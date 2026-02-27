import json
import logging
import re
from re import Pattern
from typing import Annotated, Dict, List, Optional, Type, TypeAlias, Union

import xxhash
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


def create_row_hash(record: dict, sorted_keys: tuple[str]) -> bytes:
    data_string = "|".join(
        "" if record.get(key) is None else str(record[key]) for key in sorted_keys
    )
    return xxhash.xxh128(data_string.encode("utf-8")).digest()


class JSONParser:
    def __init__(self, models: list[Type[SQLModel]]):
        self._initialized: bool = False
        self._index_pattern = re.compile(r"\[(\d+)\]")
        self._indexed_json: dict[str, JsonValue] = {}
        self._models_records: dict[str, list[dict]] = {}

        self._cached_models_fields: dict[str, list[str]] = {}
        self._cached_models_sorted_keys: dict[str, list[str]] = {}
        self._cached_models_adapters: dict[str, TypeAdapter] = {}
        self._cached_models_json_path_patterns: dict[str, str] = {}
        self._cached_models_regex_patterns: dict[str, Pattern] = {}
        self._cached_alias_paths_combined: Optional[Pattern] = None
        self._initialize(models)

    def _model_specs_find_deepest_common_path_pattern(self, aliases: list[str]) -> str:
        paths = [".".join(alias.split(".")[:-1]) for alias in aliases]
        path_segments = [path.split(".") for path in paths]
        common_segments = []
        min_length = min(len(segments) for segments in path_segments)

        for index in range(min_length):
            segments_at_position = [segments[index] for segments in path_segments]
            first_segment = segments_at_position[0]
            first_base = (
                first_segment.split("[")[0] if "[" in first_segment else first_segment
            )

            if all(
                seg.split("[")[0] == first_base if "[" in seg else seg == first_base
                for seg in segments_at_position
            ):
                common_segments.append(first_segment)
            else:
                break

        return ".".join(common_segments) if common_segments else "root"

    def _model_specs_find_deepest_wildcard_path(self, aliases: list[str]) -> str:
        return max(
            (".".join(alias.split(".")[:-1]) for alias in aliases),
            key=lambda p: p.count("."),
        )

    def _initialize(self, models: list[Type[SQLModel]]) -> None:
        if not self._initialized:
            seen_aliases = set()
            for model in models:
                model_name = model.__name__
                self._cached_models_fields[model_name] = []
                self._models_records[model_name] = []
                self._cached_models_regex_patterns[model_name] = {}

                sorted_keys = []
                wildcard_aliases = []
                aliases = []

                for field_name, field_info in sorted(model.model_fields.items()):
                    alias = field_info.alias
                    if alias is None:
                        raise ValueError(
                            f"Alias (JsonPath) is required for field {field_name} in model {model_name}"
                        )
                    seen_aliases.add(alias)
                    has_wildcard: bool = "[*]" in alias
                    if has_wildcard:
                        wildcard_aliases.append(alias)
                    self._cached_models_fields[model_name].append(
                        (field_name, alias, has_wildcard)
                    )
                    sorted_keys.append(field_name)
                    aliases.append(alias)

                self._cached_models_sorted_keys[model_name] = tuple[str](sorted_keys)

                if wildcard_aliases:
                    json_path_pattern = self._model_specs_find_deepest_wildcard_path(
                        wildcard_aliases
                    )
                else:
                    json_path_pattern = (
                        self._model_specs_find_deepest_common_path_pattern(aliases)
                    )

                self._cached_models_json_path_patterns[model_name] = json_path_pattern

                # NOTE: TypeAdapter does not like SQLModels
                safe_model = Annotated[model, BeforeValidator(model.model_validate)]
                self._cached_models_adapters[model_name] = TypeAdapter(safe_model)

            pattern_strs = (
                re.escape(a).replace(r"\[\*\]", r"\[\d+\]") for a in seen_aliases
            )
            self._cached_alias_paths_combined = re.compile(
                "^(?:" + "|".join(pattern_strs) + ")$"
            )
            self._initialized = True

    def _path_is_needed(self, path: str) -> bool:
        return self._cached_alias_paths_combined.fullmatch(path) is not None

    def _clear_indexed_json(self) -> None:
        self._indexed_json = {}

    def _clear_models_records(self) -> None:
        for model_name in self._models_records:
            self._models_records[model_name] = []

    def _parsing_path_matches(self, path: str, pattern: str, model_name: str) -> bool:
        if pattern not in self._cached_models_regex_patterns[model_name]:
            escaped = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
            self._cached_models_regex_patterns[model_name][pattern] = re.compile(
                escaped
            )
        return bool(
            self._cached_models_regex_patterns[model_name][pattern].fullmatch(path)
        )

    def _parsing_replace_wildcard_with_index(
        self, alias_path: str, current_path: str
    ) -> str:
        alias_segments = alias_path.split(".")
        current_segments = current_path.split(".")
        resolved_segments = []
        current_index = 0

        for alias_segment in alias_segments:
            if "[*]" in alias_segment:
                key_name = alias_segment.split("[")[0]
                found = False
                for index in range(current_index, len(current_segments)):
                    seg = current_segments[index]
                    if seg.startswith(key_name + "["):
                        match = self._index_pattern.search(seg)
                        if match:
                            resolved_segments.append(f"{key_name}[{match.group(1)}]")
                            current_index = index + 1
                            found = True
                            break
                if not found:
                    resolved_segments.append(alias_segment)
            else:
                resolved_segments.append(alias_segment)
                if (
                    current_index < len(current_segments)
                    and current_segments[current_index] == alias_segment
                ):
                    current_index += 1

        return ".".join(resolved_segments)

    def _value_for_model(self, value: JsonValue) -> JsonValue:
        """Serialize arrays to strings so model string fields accept them."""
        if isinstance(value, list):
            return json.dumps(value)
        return value

    def _parsing_build_model_data(
        self, path: str, model_name: str
    ) -> dict[str, JsonValue]:
        data = {}
        for _, alias, has_wildcard in self._cached_models_fields[model_name]:
            if has_wildcard:
                list_path = alias.replace("[*]", "")
                list_value = self._indexed_json.get(list_path)
                if isinstance(list_value, list):
                    if not list_value or not isinstance(list_value[0], dict):
                        data[alias] = json.dumps(list_value)
                    else:
                        resolved_alias = self._parsing_replace_wildcard_with_index(
                            alias, path
                        )
                        data[alias] = self._value_for_model(
                            self._indexed_json.get(resolved_alias)
                        )
                else:
                    resolved_alias = self._parsing_replace_wildcard_with_index(
                        alias, path
                    )
                    data[alias] = self._value_for_model(
                        self._indexed_json.get(resolved_alias)
                    )
            else:
                resolved_alias = alias
                data[alias] = self._value_for_model(
                    self._indexed_json.get(resolved_alias)
                )
        return data

    def _parsing_extract_models_at_path(self, path: str) -> None:
        for (
            model_name,
            json_path_pattern,
        ) in self._cached_models_json_path_patterns.items():
            if self._parsing_path_matches(path, json_path_pattern, model_name):
                try:
                    adapter = self._cached_models_adapters[model_name]
                    sorted_keys = self._cached_models_sorted_keys[model_name]

                    data = self._parsing_build_model_data(path, model_name)
                    record = adapter.validate_python(data).model_dump()
                    record["etl_row_hash"] = create_row_hash(record, sorted_keys)
                    self._models_records[model_name].append(record)
                except ValidationError as e:
                    logger.error(
                        f"Validation error for model '{model_name}' at path {path}: {e}"
                    )
                    raise e

    def _parsing_walk(self, obj: JsonValue, path: str = "root") -> None:
        if path != "root" and self._path_is_needed(path):
            self._indexed_json[path] = obj

        if isinstance(obj, dict):
            for key, value in obj.items():
                field_path = f"{path}.{key}"
                if self._path_is_needed(field_path):
                    self._indexed_json[field_path] = value
                if isinstance(value, (dict, list)):
                    self._parsing_walk(value, field_path)

            self._parsing_extract_models_at_path(path)

        elif isinstance(obj, list):
            for index, item in enumerate(obj):
                item_path = f"{path}[{index}]"
                if self._path_is_needed(item_path):
                    self._indexed_json[item_path] = item
                if isinstance(item, (dict, list)):
                    self._parsing_walk(item, item_path)

    def parse(self, json_data: JsonValue) -> dict[str, list[dict]]:
        if isinstance(json_data, list):
            self._clear_models_records()
            for json_obj in json_data:
                self._clear_indexed_json()
                self._parsing_walk(json_obj)
        elif isinstance(json_data, dict):
            self._clear_models_records()
            self._clear_indexed_json()
            self._parsing_walk(json_data)
        else:
            raise ValueError("Input JSON data must be a list or dict")
        return self._models_records
