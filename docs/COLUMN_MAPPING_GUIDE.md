# Column Mapping Guide

The engine uses five standardized inputs. A connected system can use different source column names, but each must map to the correct standard field.

| Standard field | Required | Expected form | Example |
|---|---:|---|---|
| `lead_source` | Yes | Category/text | Referral |
| `engagement_level` | Yes | Category/text | High |
| `interest_level` | Yes | Category/text | Medium |
| `requirement_fit` | Yes | Category/text | High |
| `days_since_interaction` | Yes | Numeric days, or parseable date | 4 |
| `lead_id` | No | Unique source ID | CRM-1004 |
| `conversion_status` | No | Outcome category | Converted / Lost |

## Data quality recommendations

- Use consistent labels such as High, Medium and Low.
- Avoid mixing unrelated concepts in one column.
- Keep missing values blank; do not invent values.
- For day counts, use non-negative numeric values.
- Ensure each `lead_id` is unique in the source system.
- Confirm outcome labels mean actual sale/client conversion, not merely a contacted or qualified lead.
- Remove duplicate records and test for leakage before training.

## Example

Source CSV:

```csv
CRM_ID,Channel,Activity,Intent,Product_Match,Days_Ago,Deal_Result
CRM-1,Referral,High,High,High,1,Converted
CRM-2,Website,Low,Medium,Low,12,Lost
```

Mapping:

```json
{
  "lead_id": "CRM_ID",
  "lead_source": "Channel",
  "engagement_level": "Activity",
  "interest_level": "Intent",
  "requirement_fit": "Product_Match",
  "days_since_interaction": "Days_Ago",
  "conversion_status": "Deal_Result"
}
```
