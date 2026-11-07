# API Integration Guide

This guide explains the intended integration pattern for a CRM, ERP, sales portal or Google Sheets-backed application.

## Recommended flow

1. Export or query lead records from the source system.
2. Translate source columns into the five standard model parameters.
3. Send historical labelled leads to `/api/train`.
4. Send new or changed leads to `/api/predict`.
5. Match each result to the original record using `lead_id`.
6. Display the returned priority and prediction in the source CRM.
7. Periodically collect final outcomes and retrain using an approved training process.

## Mapping contract

| Universal field | Example source fields |
|---|---|
| `lead_source` | Lead Source, Campaign, Channel |
| `engagement_level` | Activity Band, Calls/Meetings Band, Engagement |
| `interest_level` | Interest, Enquiry Temperature, Customer Intent |
| `requirement_fit` | Product Fit, Requirement Match, Need Fit |
| `days_since_interaction` | Days Since Contact, Last Contact Age |

Use numeric day counts for `days_since_interaction` where possible. Date strings are supported as a fallback, but numeric day counts are more reproducible.

## Example mapping object

```json
{
  "lead_id": "LeadID",
  "lead_source": "Source",
  "engagement_level": "Engagement",
  "interest_level": "Interest",
  "requirement_fit": "Fit",
  "days_since_interaction": "DaysSinceLastCall",
  "conversion_status": "FinalStatus"
}
```

## Important integration rules

- Preserve the source system's lead ID; never use a row number as a permanent CRM identifier.
- Keep the same meaning and scale for categories across training and prediction.
- Normalize status values before training.
- Do not use future information (for example, final sale date or a post-conversion activity) as an input feature.
- Only send the five model inputs plus the optional record ID and outcome field.
- Treat predictions as decision support, not an instruction to ignore leads with lower scores.
- V1 returns prediction results to the caller. Writing them back into the CRM must be implemented by the integrating application.

## Current V1 integration boundary

V1 supports CSV upload APIs. Direct database connectors, webhooks, scheduled synchronization, OAuth integrations and CRM write-back are not included yet.
