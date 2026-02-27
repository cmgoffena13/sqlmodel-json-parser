import json

from parser import JSONParser
from tests.fixtures.nested_json import ARRAY_OF_NESTED_JSON
from tests.models import Invoice, InvoiceItem, InvoiceItemTransaction

data_models = [Invoice, InvoiceItem, InvoiceItemTransaction]

parser = JSONParser(data_models)

results = parser.parse(ARRAY_OF_NESTED_JSON)


print("=" * 100)
print("JSON Parser Mapping (For Last Record)")
print("=" * 100)
print(json.dumps(parser._indexed_json, indent=4))
print("=" * 100)
print(f"Invoice Model Results - Total Records: {len(results['Invoice'])}")
print("=" * 100)
print(results["Invoice"])
print("=" * 100)
print(f"InvoiceItem Model Results - Total Records: {len(results['InvoiceItem'])}")
print("=" * 100)
print(results["InvoiceItem"])
print("=" * 100)
print(
    f"InvoiceItemTransaction Model Results - Total Records: {len(results['InvoiceItemTransaction'])}"
)
print("=" * 100)
print(results["InvoiceItemTransaction"])
