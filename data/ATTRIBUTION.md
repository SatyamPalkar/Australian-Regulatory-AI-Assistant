# Statutory source attribution

The active collection contains selected sections of Schedule 2 (Australian Consumer
Law) of the **Competition and Consumer Act 2010**, sourced through
[cchew/lex-au on Hugging Face](https://huggingface.co/datasets/cchew/lex-au).

- Dataset maintainer: **cchew**. The dataset converts Commonwealth legislation to
  Akoma Ntoso XML. See its dataset card for conversion limitations.
- Original source and copyright: **Commonwealth of Australia**, Federal Register
  of Legislation. Source compilation **C2026C00389**, effective **27 August 2026**.
- Dataset revision: `ce532ddeb514fa477d6466a892fa17e62d21513e`.
- Licence: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
- Changes in this project: selection of specified statutory sections, XML markup
  removal, whitespace normalisation, retrieval chunking and added provenance.
  The project does not author summaries or alter substantive wording in this collection.
- [Pinned XML source](https://huggingface.co/datasets/cchew/lex-au/blob/ce532ddeb514fa477d6466a892fa17e62d21513e/xml/competition-and-consumer-act-2010.xml).
- [Original law, source version](https://www.legislation.gov.au/C2004A00109/2026-08-27/text).
- [Latest official law](https://www.legislation.gov.au/C2004A00109/latest/text).

The collection is a dataset snapshot, not an official publication or a guarantee
of the current law. Check the original source and later amendments. It covers
selected national consumer-law provisions relevant to Sydney and NSW. State-only
Acts, council by-laws, tribunal fees and complaint-service locations are outside
this collection.

When checked on 28 October 2026, the official register listed a newer compilation,
**C2026C00405**, dated **16 September 2026**. Changes to the selected sections have
not been compared. The dataset's August version remains explicitly labelled.

The separate `demo.jsonl` file retains the original project-authored ACCC summaries
for historical baseline tests. It is not the active hosted corpus.
