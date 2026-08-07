# US-014 Feature Screening for Proxy and Bias Variables

## Summary

This document screens every model feature for encoded inequity and proxy risk before the models are used
for any targeting. It is a required ethics step for this project, not a checkbox: social determinants of
health (SDoH) variables carry the imprint of historical inequity, and geographic variables can stand in for
race even when race is never recorded. Here we state the screening method, record a verdict for every
feature the two models use, give the reasoning for the borderline features, and cite the research the
method rests on.

This is input-side screening. It is different from the rurality fairness analysis in US-018
(`fairness_by_rurality` in `src/model/train.py`, and the fairness section of `documents/modeling.md`), which measures a trained model's output
across rural and less-rural strata. US-018 asks whether the model performs unequally after the fact. US-014
asks, before that, whether any single feature is an inequity proxy we should not be feeding the model in the
first place. The two are complementary and neither replaces the other.

## What is and is not in the model

The feature lists are the versioned source of truth in `src/model/config.py`.

- County model, `COUNTY_FEATURES`: `food`, `access`, `economic`, `education`, `environment`,
  `hpsaScore`, `rural`, `needIndex`.
- Patient model, `PATIENT_FEATURES`: `age`, `sys`, `dia`, `a1c`, `ctx_food`, `ctx_access`,
  `rural`, `needIndex`.

First finding, from a direct search of the feature builders and the served data: no race, ethnicity, or ZIP
field is used as a predictor anywhere. Geography enters the pipeline only as the `county_fips` join key in
`src/transform/geographic_join.py`, and it is used to attach community context, never as a model input on
its own. That removes the most direct form of the problem but not the indirect one, which is what the rest
of this screen is about.

Three SDoH domains were screened here before they went live, so the decision was on record before they
could influence a result. All three have since shipped: `economic` and `education` carry real Census ACS
signal (US-013), and `environment` is the CDC/ATSDR EJI Environmental Burden Module percentile (US-009).
They now sit in `COUNTY_FEATURES` and their monitoring obligation is active.

## Screening method

Each feature is evaluated on three questions.

1. Does the feature directly encode a protected attribute (race, ethnicity, disability, or an attribute used
   as an unlawful basis)? A yes here is disqualifying.
2. Is the feature a plausible proxy for a protected attribute? SDoH and geographic measures track
   residential segregation and historical disinvestment, so a feature can carry a protected signal without
   naming it.
3. Is the feature's inclusion justified as a clinically or structurally meaningful, and ideally actionable,
   risk signal that a clinic could respond to?

From those answers each feature gets one of three verdicts.

- Keep: clinically or structurally justified with low proxy risk.
- Keep with monitoring: justified and useful, but it carries proxy risk that has to be watched through the
  US-018 rurality slice and revisited as new data arrives. This is the honest label for most SDoH features,
  because the inequity they measure is real and is the thing the clinic is trying to address, yet the same
  measure can encode who has historically been underserved.
- Exclude: proxy risk is not offset by justification, or the feature is a constant placeholder with no signal.

The borderline features are the ones that land on "Keep with monitoring" for a substantive reason, and each
of those gets its own paragraph below.

## Per-feature screen

| Feature | Model | Type | Direct protected attribute | Proxy risk | Verdict |
| --- | --- | --- | --- | --- | --- |
| `age` | patient | clinical | no | low | Keep |
| `sys` (systolic BP) | patient | clinical | no | low | Keep |
| `dia` (diastolic BP) | patient | clinical | no | low | Keep |
| `a1c` | patient | clinical | no | low | Keep |
| `hpsaScore` | county | structural capacity | no | low to moderate | Keep |
| `food` (dom.food) | county | SDoH | no | moderate | Keep with monitoring |
| `access` (dom.access) | county | SDoH | no | moderate | Keep with monitoring |
| `ctx_food` | patient | SDoH context | no | moderate | Keep with monitoring |
| `ctx_access` | patient | SDoH context | no | moderate | Keep with monitoring |
| `rural` | both | geographic | no | high | Keep with monitoring |
| `needIndex` | both | SDoH composite | no | moderate to high | Keep with monitoring |
| `economic` (live, US-013) | county | SDoH | no | moderate to high | Keep with monitoring |
| `education` (live, US-013) | county | SDoH | no | moderate to high | Keep with monitoring |
| `environment` (live, US-009) | county | SDoH, environmental justice | no | high | Keep with monitoring |

The clinical features (`age`, `sys`, `dia`, `a1c`) are direct physiological risk factors for the chronic
conditions this project is about, and they are not stand-ins for a protected attribute in a clinical-risk
setting, so they are kept without a monitoring caveat. Everything with a monitoring caveat is discussed next.

## Borderline features and the reasoning

### `rural`

`rural` is the county's USDA ERS Rural-Urban Continuum Code for 2023, normalized to a 0 to 1 scale
(US-007). It replaced the population-percentile proxy this screen originally covered; the verdict carries
over because the proxy risk is a property of rurality itself, not of how it is measured. It is the highest
proxy-risk feature we keep, and we keep it deliberately.

The risk is real. Geography is one of the best-documented proxies for race in the United States, because
residential segregation means where a person lives is correlated with race even when race is never recorded
(Bailey et al. 2017; Krieger et al. 2003). Rurality specifically also tracks age, income, and the racial
composition of a region, so a rurality feature can carry more than distance to care.

We still keep it, for two reasons. First, rurality is the explicit primary equity axis of this whole project,
so removing it would blind the model to the exact population it exists to serve. Second, the honest way to
manage a feature that is both important and risky is to keep it and watch it, not to drop it and lose the
ability to measure the disparity. Our resolution is a rule: `rural` is used as a model predictor and as the
US-018 fairness stratifier, and it is never turned into a standalone targeting rule on its own. The US-018
slice caught exactly the kind of disparity this monitoring exists for: under the old proxy the county model
was weaker on more-rural counties (0.54 versus 0.78 PR-AUC). After the real economic, education, and
environment signal landed and rurality was locked to RUCC, the direction reversed (about 0.95 more-rural
versus 0.78 less-rural); `documents/modeling.md` has the full account. The gap is documented rather than
buried, in both directions.

### `needIndex`

`needIndex` is the weighted composite of the SDoH domains on a 0 to 100 scale. It carries two concerns. It
inherits the proxy risk of every domain it aggregates, and because it is a composite it hides which domain
is actually driving a result, which makes a biased contribution harder to see.

We keep it with monitoring, and we already act on the second concern: `needIndex` is deliberately left out of
the county driver labels (`COUNTY_DRIVER_LABELS` in `config.py`) so that explanations point at the underlying actionable factors
(care access, food burden, provider shortage) rather than restating a black-box composite. It stays a
predictor for ranking, but it is not allowed to be the explanation. If the domain weights change, this
feature should be re-screened, because reweighting a composite can quietly change whose need it emphasizes.

### `food`, `access`, `ctx_food`, `ctx_access`

These are the food-access and care-access SDoH burdens, at the county level (`food`, `access`) and attached
to each patient as county context (`ctx_food`, `ctx_access`). They measure structural conditions that are
correlated with historical disinvestment and, through segregation, with race (Braveman and Gottlieb 2014).
That is exactly why they are useful: they name a concrete, addressable community need. We keep them with
monitoring rather than excluding them, because the burden they measure is the thing the clinic is trying to
reduce, and pretending it is race-neutral would be worse than naming it and watching it.

The two `ctx_*` features carry an extra caveat. They assign a county-level burden to an individual patient,
which is an ecological inference: not every patient in a high-burden county carries that burden personally
(Diez Roux and Mair 2010). We keep them because county context is the best community signal available in a
non-PHI design, but the patient model's context features should be read as community-level risk attached to a
person, not as a measured personal circumstance, and the UI already frames patient results as synthetic and
context-driven.

### `economic`, `education`, `environment` (screened before launch, now live)

These three domains were screened before they entered the model, so the decision was on record first.
`economic` (poverty, uninsured, unemployment, and median income) and `education` (share without a high
school diploma) are strong structural-inequity measures, correlated with race through the same segregation
channel as the other SDoH features; both went live under US-013 from the Census ACS feed. `environment` is
the CDC/ATSDR EJI Environmental Burden Module percentile, an environmental-justice index that is
intentionally built to track disparity by race and income, wired under US-009. All three get the same
verdict as the SDoH features already in the model: Keep with monitoring. They now carry real variance and
sit in `COUNTY_FEATURES`, so that monitoring obligation is active, not prospective.

## What monitoring means in practice

"Keep with monitoring" is only meaningful if something actually happens. For this project it means three
concrete commitments. The US-018 rurality slice is run on every training run and its gap is reported, not
hidden. Any change to the SDoH domain set or the `needIndex` weights triggers a re-screen using this same
method, because a new or reweighted feature is a new proxy question. And the model output is never used as an
automated targeting or eligibility rule: every recommendation stays reviewable and overridable by a provider
(the human-in-the-loop constraint in US-022), which is the backstop for a proxy effect this screen does not
catch.

## Research basis

- Bailey ZD, Krieger N, Agenor M, Graves J, Linos N, Bassett MT. Structural racism and health inequities in
  the USA: evidence and interventions. The Lancet, 2017. Residential segregation as a driver of health
  inequity and why geography carries a racial signal.
- Krieger N, Chen JT, Waterman PD, Rehkopf DH, Subramanian SV. Race/ethnicity, gender, and monitoring
  socioeconomic gradients in health: a comparison of area-based socioeconomic measures (the Public Health
  Disparities Geocoding Project). American Journal of Public Health, 2003. How area-based measures relate to
  race and socioeconomic position.
- Braveman P, Gottlieb L. The social determinants of health: it's time to consider the causes of the causes.
  Public Health Reports, 2014. Why SDoH measures encode upstream structural inequity.
- Obermeyer Z, Powers B, Vogeli C, Mullainathan S. Dissecting racial bias in an algorithm used to manage the
  health of populations. Science, 2019. A worked example of a health algorithm carrying racial bias through a
  proxy variable, and why the choice of feature matters.
- Gianfrancesco MA, Tamang S, Yazdany J, Schmajuk G. Potential biases in machine learning algorithms using
  electronic health record data. JAMA Internal Medicine, 2018. Sources of bias in clinical prediction models
  and how to screen for them.
- Diez Roux AV, Mair C. Neighborhoods and health. Annals of the New York Academy of Sciences, 2010. The
  ecological-inference caveat for assigning neighborhood context to individuals.
- USDA Economic Research Service, Rural-Urban Continuum Codes documentation. Reference for how rurality is
  defined; since US-007 the `rural` feature uses the RUCC 2023 codes directly rather than a population-based
  approximation.

## Status against the US-014 acceptance criteria

- Each feature screened for encoded inequity: done, in the per-feature table and the borderline section.
- Screening method documented: done, the three-question method above.
- Borderline-feature decisions recorded with reasoning: done, `rural`, `needIndex`, the `ctx_*` and SDoH
  features, and the three domains screened before launch each have a recorded verdict and reasoning.
- Research basis cited: done, the reference list above.
