# Anywhere rule operands

`rules -e/-i --anywhere` is shorthand for prepending `**/` to each reusable
operand before normal profile/current-directory scoping. `--any` uses ordinary
option abbreviation. `--pattern` and `--anywhere` are mutually exclusive.

This provides a readable way to match current and future names at any depth
without introducing a new stored rule type or matching engine. Global rules
are rooted in each profile; remote targeting retains its existing semantics.
Multiple operands and comma separation use the shared operand normalization.

It does not mean outside the current scope, expand against current files,
or change rule precedence. Quote wildcard operands to prevent shell expansion.
