# SQLModel JSON Parser

A fast and efficient JSON Parser designed to split out JSON data into multiple SQLModels / Tables; Perfect for ETL workloads to validate data and populate tabular tables.

The Parser utilizes aliasing to declare the JSON path of the field. The Parser builds an indexed mapping of the JSON while it walks through, while being aware of its positioning, allowing for easy assignment of values from any nested level of the JSON, making foreign keys a breeze.

All the code is found in `parser.py`

## How to Use

### SQLModel Code

Simply add the json path as an alias for the field.

```python
class Invoice(SQLModel, table=True):
    id: str = Field(primary_key=True, alias="root.id")
    total_amount: float = Field(alias="root.total_amount")
    latitude: Optional[float] = Field(alias="root.geo.latitude", nullable=True)
    longitude: Optional[float] = Field(alias="root.geo.longitude", nullable=True)

class InvoiceItem(SQLModel, table=True):
    invoice_id: str = Field(foreign_key="invoice.id", alias="root.id")
    id: str = Field(primary_key=True, alias="root.invoice_items[*].id")
    sku: str = Field(alias="root.invoice_items[*].sku")
    description: Optional[str] = Field(
        alias="root.invoice_items[*].description", nullable=True
    )
    quantity: int = Field(alias="root.invoice_items[*].quantity")
    unit_price: float = Field(alias="root.invoice_items[*].unit_price")
    tags: str = Field(alias="root.invoice_items[*].tags", nullable=True)

class InvoiceItemTransaction(SQLModel, table=True):
    tx_id: str = Field(
        primary_key=True, alias="root.invoice_items[*].transactions[*].tx_id"
    )
    invoice_item_id: str = Field(
        foreign_key="invoiceitem.id", alias="root.invoice_items[*].id"
    )
    invoice_id: str = Field(foreign_key="invoice.id", alias="root.id")
    amount: float = Field(alias="root.invoice_items[*].transactions[*].amount")
    payment_method: str = Field(
        alias="root.invoice_items[*].transactions[*].payment_method"
    )
    timestamp: datetime = Field(alias="root.invoice_items[*].transactions[*].timestamp")
```

### Execution Code
```python
# See `tests/models.py` 
data_models = [Invoice, InvoiceItem, InvoiceItemTransaction]

# Initialize the Parser (Caches metadata from the models)
parser = JSONParser(data_models)

response = httpx.get("https://example.api.com/invoices")

# Can be an individual JSON object or an array of JSON objects
json_data = response.json()

# Parse the JSON, Split it out, and Validate each record
results = parser.parse(json_data)

# Each key of "results" maps back to the name of the SQLModels
# Each value is a list of validated dictionaries
# {"Invoice": [{"id": 123, ...}, {"id": 124, ...}], "InvoiceItem": [...], "InvoiceItemTransaction": [...]}
print(results)
```

## Validation

The Parser validates the JSON against the SQLModels as well. If the data cannot conform to the model, then it cannot conform to a table either and the parser will break with a pydantic ValidationError.

## Alias Syntax Examples

- `root.id`: grabs the `id` field in the JSON object root level (ex. invoice_id)
- `root.geo.latitude`: grabs the `latitude` field in the geo JSON dict within the JSON object 
- `root.invoice_items[*].id`: grabs ALL the `id` fields found within the invoice_items array within the JSON object
- `root.invoice_items[*].transactions[*].tx_id`: grabs ALL the `tx_id` fields found within the transactions array that is within each object of the invoice_items array within the JSON object
- `root.invoice_items[*].tags`: this grabs the `tags` array fields within the invoice_items array. Due to data type limitations, if an array is pulled, it is always cast to a string.

The `*` wildcard symbol represents any index within the array, which means you can end up with multiple records for a model (one record for each index found in the array) from a single nested JSON object.  

> **Note:** Every field must have an alias and every alias path needs `root` in front of it.

## Example

Run `example.py` to see the parser's mapping and the results of the records that map to the SQLModel classes. 