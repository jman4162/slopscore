# Security Policy

## Reporting a vulnerability

Email security reports to jhodge007@gmail.com instead of opening a public issue. Include the
version, a description, and steps to reproduce. You can expect an acknowledgement within a few days.

## Scope

slopscore reads untrusted text and runs regex rule packs over it. The regex patterns are bounded
and the engine is backtracking-resistant, but if you find an input that causes excessive runtime or
memory, or any other safety issue, please report it.
