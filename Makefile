.RECIPEPREFIX := >
.PHONY: run preview settings check install uninstall package release-check

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

package:
> python3 tools/package.py build --output .runtime/package

release-check:
> python3 tools/release.py check
