# SQLModel JSON Parser

A fast and efficient JSON Parser designed to split out JSON data into multiple SQLModels / Tables; Perfect for ETL workloads to validate data and populate tabular tables.

The Parser utilizes aliasing to declare the JSON path of the field. The Parser builds an indexed mapping of the JSON while it walks through, while being aware of its positioning, allowing for easy assignment of values from any nested level of the JSON, making foreign keys a breeze.

All the code is found in `parser.py`

## How to Use

```python
# See `tests/models.py` 
data_models = [Invoice, InvoiceItem, InvoiceItemTransaction]

# Initialize the Parser (Caches metadata from the models)
parser = JSONParser(data_models)

response = httpx.get("https://example.api.com/invoices")
json_data = response.json()

# Parse the JSON, Split Out, and Validate
results = parser.parse(json_data)

# Each key of "results" maps back to the name of the SQLModels
# Each value is a list of validated dictionaries
# {"Invoice": [{"id": 123, ...}, {"id": 124, ...}], "InvoiceItem": [...], "InvoiceItemTransaction": [...]}
print(results)
```

## Validation

The Parser validates the JSON against the SQLModels as well. If the data cannot conform to the model, then it cannot conform to a table either and the parser will break with a pydantic ValidationError.

## ETL Row Hash

The Parser automatically takes all columns and adds an `etl_row_hash` to each record, which is a hash value (in bytes) of all the values in the row. This allows for easy comparison for updates within an ETL process.

## Syntax Examples

- `root.id`: grabs the `id` field in the JSON object root level
- `root.invoice_items[*].id`: grabs ALL the `id` fields found within the invoice_items array within the JSON object
- `root.invoice_items[*].transactions[*].tx_id`: grabs ALL the `tx_id` fields found within the transactions array that is within each object of the invoice_items array within the JSON object
- `root.invoice_items[*].tags`: this grabs the `tags` array fields within the invoice_items array. Due to data type limitations, if an array is pulled, it is always cast to a string.

The `*` wildcard symbol represents any index within the array, which means you can end up with multiple records for a model from a single nested JSON object.  

> **Note:** Every field must have an alias and every path needs `root` in front of it.

## Example

Run `example.py` to see the parser's mapping and the results of the records that map to the SQLModel classes. 