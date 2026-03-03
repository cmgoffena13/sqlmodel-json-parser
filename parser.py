import json
import logging
import re
from typing import Annotated, Dict, List, Optional, Pattern, Type, TypeAlias, Union

from pydantic import BeforeValidator, TypeAdapter, ValidationError
from sqlmodel import SQLModel

JsonValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    List["JsonValue"],
    Dict[str, "JsonValue"],
]

logger = logging.getLogger(__name__)


class JSONParser:
    def __init__(self, models: list[Type[SQLModel]]):
        self._initialized: bool = False
        self._json_map: Dict[str, str] = {}
        self._models_records: dict[str, list[dict]] = {}

        self._cached_index_pattern = re.compile(r"\[(\d+)\]")
        self._cached_models_fields: dict[str, list[str]] = {}
        self._cached_models_common_path_regex: dict[str, Pattern] = {}
        self._cached_models_adapters: dict[str, TypeAdapter] = {}
        self._cached_all_aliases_regex: Optional[Pattern] = None
        self._initialize_parser(models)

    def _find_deepest_common_path_pattern(self, aliases: list[str]) -> str:
        """
        Finds the deepest common path pattern in a list of aliases.
        """
        paths = [".".join(alias.split(".")[:-1]) for alias in aliases]
        paths_path_pieces = [path.split(".") for path in paths]
        min_length = min(len(pieces) for pieces in paths_path_pieces)
        common_path_pieces = []

        for index in range(min_length):
            current_pieces = [path_pieces[index] for path_pieces in paths_path_pieces]
            if all(piece == piece[0] for piece in current_pieces):
                common_path_pieces.append(current_pieces[0])
            else:
                break
        return ".".join(common_path_pieces) if common_path_pieces else "root"

    def _find_deepest_wildcard_path_pattern(self, aliases: list[str]) -> str:
        """
        Finds the deepest wildcard path pattern in a list of aliases.
        """
        paths = [".".join(alias.split(".")[:-1]) for alias in aliases]
        deepest_path = max(paths, key=lambda p: p.count("."))
        return deepest_path

    def _initialize_parser(self, models: list[Type[SQLModel]]) -> None:
        if not self._initialized:
            seen_aliases = set()
            for model in models:
                model_name = model.__name__
                self._cached_models_fields[model_name] = []
                self._models_records[model_name] = []
                self._cached_models_common_path_regex[model_name] = {}

                wildcard_aliases = []
                aliases = []

                for field_name, field_info in model.model_fields.items():
                    alias = field_info.alias
                    if alias is None:
                        raise ValueError(
                            f"Alias (JsonPath) is required for field {field_name} in model {model_name}"
                        )
                    seen_aliases.add(alias)
                    has_wildcard = "[*]" in alias
                    if has_wildcard:
                        wildcard_aliases.append(alias)
                    else:
                        aliases.append(alias)
                    self._cached_models_fields[model_name].append((alias, has_wildcard))

                if wildcard_aliases:
                    json_path_pattern = self._find_deepest_wildcard_path_pattern(
                        wildcard_aliases
                    )
                else:
                    json_path_pattern = self._find_deepest_common_path_pattern(aliases)
                self._cached_models_common_path_regex[model_name] = re.compile(
                    re.escape(json_path_pattern).replace(r"\[\*\]", r"\[\d+\]")
                )

                # NOTE: TypeAdapter does not like SQLModels
                safe_model = Annotated[model, BeforeValidator(model.model_validate)]
                self._cached_models_adapters[model_name] = TypeAdapter(safe_model)

            pattern_strs = (
                re.escape(a).replace(r"\[\*\]", r"\[\d+\]") for a in seen_aliases
            )
            self._cached_all_aliases_regex = re.compile(
                "^(?:" + "|".join(pattern_strs) + ")$"
            )

            self._initialized = True

    def _path_in_aliases(self, path: str) -> bool:
        return self._cached_all_aliases_regex.fullmatch(path) is not None

    def _resolve_wildcard_alias(self, alias: str, path: str) -> str:
        alias_pieces = alias.split(".")
        path_pieces = path.split(".")
        resolved_pieces = []

        path_cursor = 0
        for alias_piece in alias_pieces:
            if "[*]" in alias_piece:
                key = alias_piece.split("[")[0]
                index_found = False
                for index in range(path_cursor, len(path_pieces)):
                    current_path_piece = path_pieces[index]
                    if current_path_piece.startswith(key + "["):
                        match = self._cached_index_pattern.search(current_path_piece)
                        if match:
                            resolved_pieces.append(f"{key}[{match.group(1)}]")
                            path_cursor = index + 1
                            index_found = True
                            break
                if not index_found:
                    raise ValueError(f"Wildcard alias {alias} not found in path {path}")
            else:
                resolved_pieces.append(alias_piece)
                if (
                    path_cursor < len(path_pieces)
                    and path_pieces[path_cursor] == alias_piece
                ):
                    path_cursor += 1

        resolved_alias = ".".join(resolved_pieces)
        return resolved_alias

    def _extract_values_from_json_map(self, model_name: str, path: str) -> Dict:
        data = {}
        for alias, has_wildcard in self._cached_models_fields[model_name]:
            if has_wildcard:
                resolved_alias = self._resolve_wildcard_alias(alias, path)
                value = self._json_map.get(resolved_alias)
            else:
                value = self._json_map.get(alias)

            # NOTE: If list, convert to string for general compatibility
            if isinstance(value, list):
                value = json.dumps(value)

            data[alias] = value
        return data

    def _extract_models_records(self, path: str) -> None:
        for model_name, pattern in self._cached_models_common_path_regex.items():
            if pattern.fullmatch(path):
                data = self._extract_values_from_json_map(model_name, path)
                adapter = self._cached_models_adapters[model_name]
                try:
                    record = adapter.validate_python(data).model_dump()
                except ValidationError as e:
                    logger.error(f"Error validating data for model {model_name}: {e}")
                    raise e
                self._models_records[model_name].append(record)

    def _walk_json(self, json: JsonValue, path: str = "root") -> None:
        if path != "root" and self._path_in_aliases(path):
            self._json_map[path] = json

        if isinstance(json, dict):
            for key, value in json.items():
                field_path = f"{path}.{key}"

                if self._path_in_aliases(field_path):
                    self._json_map[field_path] = value

                if isinstance(value, (dict, list)):
                    self._walk_json(value, field_path)

            self._extract_models_records(path)

        if isinstance(json, list):
            for index, value in enumerate(json):
                field_path = f"{path}[{index}]"

                if self._path_in_aliases(field_path):
                    self._json_map[field_path] = value

                if isinstance(value, (dict, list)):
                    self._walk_json(value, field_path)

            self._extract_models_records(path)

    def _clear_models_records(self) -> None:
        for model_name in self._models_records:
            self._models_records[model_name] = []

    def _clear_json_map(self) -> None:
        self._json_map = {}

    def parse(self, json: JsonValue) -> dict[str, list[dict]]:
        if isinstance(json, list):
            self._clear_models_records()
            for json_obj in json:
                self._clear_json_map()
                self._walk_json(json_obj)
        elif isinstance(json, dict):
            self._clear_models_records()
            self._clear_json_map()
            self._walk_json(json)
        else:
            raise ValueError("Input JSON data must be a list or dict")
        return self._models_records
