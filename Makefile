.PHONY: run console test

# The project lives in track_2b/ (the Hack Apertus template keeps the Makefile there). These targets
# forward, so `make run` works from the repository root as well as from track_2b/.
run:
	$(MAKE) -C track_2b run

console:
	$(MAKE) -C track_2b console

test:
	$(MAKE) -C track_2b test
