# Customer-to-Operations Experience Tasks

## Experiment track

- [x] Add product-detail / expectation-proof experiment for the fine-art print.
- [x] Add no-account guided-brief experiment with product-specific choices.
- [x] Add proposal-submission and confirmation-email experiment.
- [x] Add proof-review and delivery-email experiments using fictitious signed links.
- [x] Add internal intake-queue, production-workspace, and asset-library experiments.

## Product and operations discovery

- [ ] Test artifact-catalog comprehension with the target buyer profile.
- [ ] Define the initial channel and whether a proposal is binding.
- [ ] Define included revisions, production times, and print fulfillment policy.
- [ ] Approve customer-facing report language and prohibited forecast claims.
- [ ] Define retention and deletion policy for buyer reference images and proofs.

## Production implementation prerequisites

- [ ] Define request, order, brief, job, asset, delivery, and proof-review schemas.
- [ ] Map the approved internal order payload to `src.fulfillment.build_order`.
- [ ] Implement rights/source validation at intake, before any customer promise.
- [ ] Select object storage and a database/search mechanism for asset metadata.
- [ ] Implement immutable asset lineage, checksum, visibility, and retention rules.
- [ ] Implement email confirmation, proof, approval, and delivery event records.
