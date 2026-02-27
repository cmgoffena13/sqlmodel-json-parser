ARRAY_OF_NESTED_JSON = [
    {
        "id": "INV-2025-12345",
        "total_amount": 1567.89,
        "geo": {"latitude": 40.7128, "longitude": -74.0060},
        "invoice_items": [
            {
                "id": "ITEM-001",
                "sku": "LAPTOP-001",
                "description": "Dell XPS 13",
                "quantity": 2,
                "unit_price": 999.99,
                "tags": ["laptop", "work", "personal"],
                "transactions": [
                    {
                        "tx_id": "TX-001A",
                        "amount": 999.99,
                        "payment_method": "credit_card",
                        "timestamp": "2025-12-01T10:30:00Z",
                    },
                    {
                        "tx_id": "TX-001B",
                        "amount": -50.00,
                        "payment_method": "refund",
                        "timestamp": "2025-12-02T14:15:00Z",
                    },
                ],
            },
            {
                "id": "ITEM-002",
                "sku": "MOUSE-101",
                "description": "Logitech MX Master 3",
                "quantity": 5,
                "unit_price": 79.99,
                "tags": ["mouse", "work", "personal"],
                "transactions": [
                    {
                        "tx_id": "TX-002A",
                        "amount": 399.95,
                        "payment_method": "paypal",
                        "timestamp": "2025-12-01T11:45:00Z",
                    }
                ],
            },
        ],
    },
    {
        "id": "INV-2025-67890",
        "total_amount": 892.44,
        "geo": {"latitude": 34.0522, "longitude": -118.2437},
        "invoice_items": [
            {
                "id": "ITEM-003",
                "sku": "DOCK-202",
                "description": "USB-C Docking Station",
                "quantity": 1,
                "unit_price": 167.95,
                "tags": ["docking station", "work", "personal"],
                "transactions": [
                    {
                        "tx_id": "TX-003A",
                        "amount": 167.95,
                        "payment_method": "credit_card",
                        "timestamp": "2025-12-01T12:20:00Z",
                    }
                ],
            },
            {
                "id": "ITEM-004",
                "sku": "KEYBOARD-301",
                "description": "Keychron K2 Wireless",
                "quantity": 2,
                "unit_price": 89.00,
                "tags": ["keyboard", "work", "personal"],
                "transactions": [
                    {
                        "tx_id": "TX-004A",
                        "amount": 178.00,
                        "payment_method": "debit_card",
                        "timestamp": "2025-12-03T09:00:00Z",
                    },
                    {
                        "tx_id": "TX-004B",
                        "amount": -89.00,
                        "payment_method": "refund",
                        "timestamp": "2025-12-04T16:30:00Z",
                    },
                ],
            },
        ],
    },
]
