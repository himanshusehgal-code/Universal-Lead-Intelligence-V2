# ML Training Guide

## V1 algorithms

- K-Means clustering is always trained to discover groups in the five-feature space.
- Random Forest classification is additionally trained when the mapped outcome column has at least 20 usable rows, both classes, and at least five examples in the minority class.
- The classifier uses a random 80/20 train/test split in V1.

## What the modes mean

### Unsupervised-only

The algorithm groups records with similar feature patterns. Cluster labels such as 1, 2, 3 are identifiers, not a ranking and not probabilities of conversion.

### Supervised

The classifier learns from historical Converted/Lost outcomes and returns an estimated conversion probability. These estimates are only as reliable as the training data, labels and validation process.

## Before relying on predictions

- Use representative records from the business and industry.
- Check the number of converted and non-converted examples.
- Evaluate precision, recall, F1 and ROC-AUC; accuracy alone can be misleading with imbalanced outcomes.
- Use a time-based holdout set for production validation.
- Check probability calibration and performance across lead sources and sales teams.
- Monitor model drift and retrain only with reviewed, correctly labelled outcomes.
- Do not compare scores from separately trained customer models as if they were directly equivalent.

## Important feature limitation

The five selected fields are a deliberately compact starting point. They may not contain enough information to predict conversion accurately for every business. Validate value and fairness before using scores to allocate sales attention.
