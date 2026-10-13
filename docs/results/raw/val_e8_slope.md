## E1 - pooled flood-class scores

| model | split | n | tau | precision | recall | F1 | IoU |
|---|---|---|---|---|---|---|---|
| cutoff_unet_v1 | val | 1145 | 0.5 | 0.788 | 0.769 | 0.779 | 0.637 |
| p7 | val | 1145 | 0.55 | 0.806 | 0.757 | 0.781 | 0.641 |

## E1 - per event (flood IoU / F1, support px)

| event | cutoff_unet_v1 | p7 |
|---|---|---|
| 279 | 0.599 / 0.749 (534536) | 0.595 / 0.746 (534536) |
| 437 | 0.596 / 0.747 (64002) | 0.603 / 0.752 (64002) |
| 520 | 0.580 / 0.734 (329243) | 0.590 / 0.742 (329243) |
| 559 | 0.518 / 0.682 (50672) | 0.493 / 0.660 (50672) |
| 1111003 | 0.088 / 0.162 (6961) | 0.099 / 0.180 (6961) |
| 1111008 | 0.747 / 0.855 (480301) | 0.759 / 0.863 (480301) |

## E2 - by slope stratum (all events pooled; IoU, support px)

| slope bin | cutoff_unet_v1 | p7 |
|---|---|---|
| 0-5 deg | 0.640 (1438527) | 0.644 (1438527) |
| 5-15 deg | 0.488 (27069) | 0.458 (27069) |
| >=15 deg | 0.123 (119) | 0.128 (119) |

## E8 - expected calibration error (validation events; T = each model's fitted temperature)

| model | T | all-class ECE, T=1 | flood ECE, T=1 | all-class ECE, fitted T | flood ECE, fitted T |
|---|---|---|---|---|---|
| cutoff_unet_v1 | 1.037 | 0.002 | 0.139 | 0.002 | 0.130 |
| p7 | 1.013 | 0.002 | 0.105 | 0.002 | 0.103 |

## E8 - flood ECE by slope stratum (validation events, fitted T; flood ECE, sampled px)

| slope bin | cutoff_unet_v1 | p7 |
|---|---|---|
| 0-5 deg | 0.130 (641561) | 0.103 (734831) |
| 5-15 deg | 0.158 (14450) | 0.091 (22566) |
| >=15 deg | 0.119 (710) | 0.080 (796) |
