.RECIPEPREFIX := >
.PHONY: run preview settings check install

run:
> ./bin/hyprlarp run

preview:
> ./bin/hyprlarp preview

settings:
> ./bin/hyprlarp settings

check:
> python3 tools/check.py

install:
> ./bin/hyprlarp install
