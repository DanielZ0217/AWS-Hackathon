# Existing medical ontologies and terminology resources

**Researched:** 2026-10-23.  
**Status:** Research and proposed integration plan. No ontology releases have been downloaded, mapped, imported into Neptune or connected to executable agents.

**Architecture follow-up:** [Layer 00's extraction contract](00-ingestion-and-knowledge-preparation.md#llm-concept-and-relationship-extraction-into-neptune) adopts GPT-6 Sol as the preferred configurable extractor and Neptune Database as the managed graph target. Its structured candidates are mapped to selected terminology, checked against source spans and reviewed before publication. The [ingestion harness](../ingestion/README.md) now implements configurable Bedrock extraction, structural/span checks, reviewed concept-key mappings and Neptune CSV export. These recommendations remain candidate ontology choices; automatic ontology parsing, code/release validation and formal reasoning are not implemented.

## Recommendation for this project

Reuse established medical concepts and identifiers, then add a small project schema for observations, evidence, claims, guidance and provenance. Start with scenario-specific subsets rather than importing every available ontology.

- Lab: LOINC for observation identifiers and UCUM for units.
- Radiology: RadLex for imaging terminology.
- Shared findings and conditions: evaluate HPO and Mondo first; add SNOMED CT when appropriate licensing and access are ready.
- Nutrition: FoodOn and CDNO can normalize food and nutrient concepts; retain retrieved guidelines for substantive guidance.
- Physio: WHO ICF can structure functional and activity limitations; retain retrieved guidance and explicit patient restrictions.
- ECG: use relevant clinical observation/finding terminology first; evaluate the older dedicated ECG ontology before depending on it.

These are candidate choices, not an adopted requirement to integrate every resource before the first demo. Formal ontology validation remains optional in the baseline.

## Resources and agent mapping

| Resource | What it supplies | Proposed use | Access / limitations | Primary source |
| --- | --- | --- | --- | --- |
| SNOMED CT | Broad clinical terminology and relationships for findings, disorders, procedures and other clinical concepts | Shared clinical vocabulary across specialists and Doctor review | Appropriate license/registration is required. SNOMED International does not charge for use in member countries, but conditions and deployment territories matter. It is not unrestricted open-source content. | [Get SNOMED CT](https://www.snomed.org/get-snomed), [licensing guide](https://docs.snomed.org/snomed-ct-practical-guides/vendor-introduction-to-snomed-ct/7-licensing) |
| LOINC | Identifiers for laboratory and clinical observations | Normalize the test or measurement discussed by lab and ECG workers | Freely available under the LOINC license; review applicable download/account requirements. A test code does not determine a diagnosis or universal reference interval. | [Getting started](https://loinc.org/start), [license](https://loinc.org/license) |
| UCUM | Unambiguous measurement-unit syntax and semantics | Validate units and compatible conversions alongside LOINC | Unit coding system, not a disease ontology. Unit compatibility alone does not establish clinical comparability; conversions may need analyte-specific information. | [Specification](https://ucum.org/ucum), [common units](https://ucum.org/docs/common-units), [license](https://ucum.org/license) |
| RadLex | Radiology terminology; related RSNA resources include imaging procedure names and common data elements | Normalize imaging findings, anatomy and procedures | RSNA describes free commercial/noncommercial licensing subject to its terms. Distinguish the full lexicon from the LOINC/RSNA Radiology Playbook for procedure names. | [RSNA RadLex](https://www.rsna.org/practice-tools/data-tools-and-standards/radlex-radiology-lexicon) |
| Human Phenotype Ontology (HPO) | Standardized terms for phenotypic abnormalities in human disease | Normalize findings across worker outputs for comparison and retrieval | Check selected release licensing, imports and coverage. Phenotype terminology and disease annotations are distinct artifacts; associations are not diagnostic rules. | [OBO Foundry HPO entry and downloads](https://obofoundry.org/ontology/hp.html) |
| Mondo Disease Ontology | Harmonized disease concepts, hierarchies and cross-resource mappings | Normalize Condition nodes and reduce duplicate disease naming | Check selected release terms and mapping predicates. Cross-reference or related mapping must not automatically become equivalence. | [OBO Foundry Mondo entry and downloads](https://obofoundry.org/ontology/mondo.html) |
| FoodOn | Food entities and classifications, with links to nutritional concepts | Normalize foods and ingredients for nutrition retrieval | Listed as CC BY 4.0 in OBO Foundry; preserve attribution and review imported-resource terms. Does not supply personalized dietary treatment rules. | [FoodOn entry](https://obofoundry.org/ontology/foodon.html), [repository](https://github.com/FoodOntology/foodon) |
| Compositional Dietary Nutrition Ontology (CDNO) | Structured terms for nutritional attributes/components and their concentration | Normalize nutrient concepts and food-composition data | Primarily supports composition datasets. Check release/license terms before import; not an individualized diet-planning engine. | [CDNO entry and downloads](https://obofoundry.org/ontology/cdno.html) |
| WHO International Classification of Functioning, Disability and Health (ICF) | Classification of functioning, disability and environmental context | Structure mobility, activity and functional limitations for physio | Classification rather than an exercise-prescription ontology. Review WHO's applicable use/licensing conditions. | [WHO ICF](https://www.who.int/classifications/international-classification-of-functioning-disability-and-health) |
| Electrocardiography Ontology (ECG) | Terms for electrocardiograms, capture methods and waveforms | Supplementary ECG annotation vocabulary | BioPortal listed the last upload as September 2014 when researched. Coverage, maintenance, download and license need evaluation before adoption; old upload date alone does not establish unusability. | [BioPortal ECG entry](https://bioportal.bioontology.org/ontologies/ECG) |
| Unified Medical Language System (UMLS) | Integration of terminology names, concepts, relationships and mappings across many vocabularies | Later cross-terminology mapping and synonym lookup | NLM account/license required; individual source restrictions still apply. Avoid importing the entire Metathesaurus for the first demo. | [NLM UMLS](https://www.nlm.nih.gov/research/umls/umlsmain.html), [Metathesaurus](https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/index.html) |

BioPortal and OBO Foundry are useful discovery catalogs, not a single blanket license for everything they host: [BioPortal](https://bioportal.bioontology.org/), [OBO Foundry](https://obofoundry.org/).

## Validation: what existing resources can help check

1. **Terminology:** Does the selected identifier exist in the pinned release? Does it match the intended test, finding, condition, food or function? Preserve ambiguous and unmapped results.
2. **Structure and constraints:** Are required fields present? Do relationships connect permitted entity types? Are units compatible? Does an evidence reference resolve?
3. **Evidence support:** Does the actual cited passage support the proposed interpretation, considering negation, timing, population and patient context? This still requires the evidence-review workflow and evaluation.

Ontology membership, a valid graph path, compatible units or a successful structural check cannot prove a diagnosis or validate hidden agent reasoning. Terminology hierarchies also do not supply every clinical relationship we want, such as finding-to-condition support or condition-to-guidance applicability. Those edges need explicit evidence and review.

[SHACL](https://www.w3.org/TR/shacl/) is an existing W3C standard for constraints over RDF graphs. If the project uses an RDF representation, a SHACL validator can check declared shapes. For the proposed Neptune property graph queried with openCypher, start with application-level schema and relationship checks. Using SHACL would require an RDF representation/mapping and a validation engine; storing a graph does not automatically run those checks.

## Proposed integration into Layers 00-05

| Layer | Proposed addition |
| --- | --- |
| 00 ingestion | Fetch approved releases, preserve licenses and hashes, extract a bounded concept subset, review mappings and publish a versioned terminology manifest. |
| 01 intake | Preserve original patient wording. Optional terminology hints must not create clinical findings or silently resolve ambiguity. |
| 02 orchestration | Pin terminology versions alongside the knowledge snapshot and pass permitted lookup tools to workers. |
| 03 analysis/retrieval | Map extracted observations to candidate concepts; validate identifiers/units; use approved synonyms and hierarchies to help retrieval. Preserve original text and evidence. |
| 04 Doctor review | Inspect mappings, ambiguity, conflicts and validation findings together with source support. A vocabulary match cannot override missing clinical evidence. |
| 05 presentation | Explain reviewed findings in plain language; retain concept and validation references in audit records. |

Use one shared graph backend. If Neptune is selected, import the needed concept nodes and explicitly supported edges through a converter/loader. Different vocabularies do not require separate graph databases. Keep original ontology files and manifests in artifact storage. Preserve the distinction between terminology relationships, mapped concepts, source-supported clinical associations and run-scoped patient observations.

Suggested concept metadata: `concept_id`, `system`, `system_version`, `preferred_label`, `synonyms`, `source_uri`, `license_ref`. Suggested mapping metadata: original text, candidate concept IDs, selected ID if any, mapping method/version, ambiguity and review status. Record mapping predicates and provenance for cross-system links; do not invent equivalent mappings.

Suggested validation result: `status`, validator/ruleset version, checked record IDs and issues with rule ID, severity, field/evidence references and explanation. Layer 03 already has `ontology_validation`; richer reports can be stored as referenced artifacts without copying full terminology releases into workflow state.

## Implementation sequence and outstanding checks

1. Select concepts needed for the synthetic patient scenario and verify release/license access.
2. Download and pin HPO/Mondo subsets first; add LOINC/UCUM and RadLex where access is ready.
3. Build parsing, concept lookup, ambiguity handling and versioned export.
4. Add deterministic identifier/unit/reference checks and test valid, invalid and ambiguous mappings.
5. Build a Neptune import adapter if that backend is adopted; verify imported relationship semantics and provenance.
6. Connect worker observation mappings and Doctor validation reports in the executable harness.
7. Add nutrition/physio terminology only where it improves the scenario; continue retrieving substantive guidance from selected references.

Download size, current release identifiers, full license terms, mapping quality, import compatibility and clinical coverage have not been exhaustively evaluated. Deployment/network access and costs for Neptune are separate setup work. The present deliverable saves the research; it does not implement or deploy this integration.
