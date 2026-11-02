.RECIPEPREFIX := >
.PHONY: run preview settings check install uninstall

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

uninstall:
> ./bin/hyprlarp uninstall
