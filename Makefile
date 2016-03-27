LOCAL_DB = postgres://fluidinfo:fluidinfo@localhost/fluidinfo-test
LOCAL_SOLR = http://localhost:8080/solr
XARGS := $(shell which parallel || which xargs) $(shell test $$(uname) = Linux && echo -r)

check-virtualenv:
	@test -n "$$VIRTUAL_ENV" || { echo "You're not in a virtualenv."; exit 1; }
	@case $$VIRTUAL_ENV in */*fluiddb) ;; *) echo "You're in the wrong virtualenv."; exit 1;; esac

check-not-running:
	@test ! -f twistd.pid || { echo "FluidDB is already running, pid `cat twistd.pid`."; exit 1; }

all:
	@echo "There is no default Makefile target right now."

apidocs: check-virtualenv
	-mkdir doc/example.com/api/html
	./bin/fluidinfo build-api-docs doc/example.com/api/templates doc/example.com/api/html
	@echo "API HTML documentation created in doc/example.com/api/html"

sphinxdocs: check-virtualenv
	$(MAKE) -C doc/example.com/sphinx/fluidDB/advanced html
	$(MAKE) -C doc/example.com/sphinx/fluidDB/description html

api: check-virtualenv
	pydoctor --make-html --html-output apidoc --add-package fluiddb

doc: check-virtualenv api apidocs sphinxdocs

start: check-not-running clean check-virtualenv check-solr-configuration dropdb createdb
	./bin/fluidinfo bootstrap-database $(LOCAL_DB)
	./bin/fluidinfo prepare-for-testing $(LOCAL_DB)
	./bin/fluidinfo delete-index $(LOCAL_SOLR)
	./bin/fluidinfo build-index $(LOCAL_DB) $(LOCAL_SOLR)
	./bin/fluidinfo clear-cache
	./bin/fluidinfo-api --logfile var/log/fluidinfo-test.log --development

stop:
	test ! -f twistd.pid || kill `cat twistd.pid`

check-unit: clean check-virtualenv check-solr-configuration dropdb createdb
	trial --rterrors fluiddb

check-integration: start
	-trial --rterrors integration.wsfe integration.fom
	kill `cat twistd.pid`

check-all: check-unit check-integration

check: check-unit

check-solr-configuration:
	./bin/check-solr-configuration

setup-solr:
	./bin/setup-solr

createdb:
	-sudo -u postgres createdb fluidinfo-test -O fluidinfo
	-sudo -u postgres createdb fluidinfo-unit-test -O fluidinfo

dropdb:
	-sudo -u postgres dropdb fluidinfo-test
	-sudo -u postgres dropdb fluidinfo-unit-test

# Currently, setup-postgres unused from within this Makefile.
# It is mentioned in our README.rst setup instructions.
setup-postgres:
	sudo -u postgres createuser -D -R -S -P fluidinfo

clean:
	rm -rf classes dist
	rm -rf var/lib var/tmp/* var/log/*
	rm -rf fluidinfo.tar.bz2
	rm -f .check-pyflakes .check-pep8
	rm -f doc/example.com/api/html/permissions.html
	rm -f doc/example.com/api/html/api.html
	rm -f doc/example.com/api/html/api_admin.html
	rm -rf doc/example.com/sphinx/fluidDB/description/_build
	rm -rf doc/example.com/sphinx/fluidDB/advanced/_build
	rm -rf apidoc
	find . -name '*~' -print0 | $(XARGS) -0 rm
	find . \( -name '*.py[co]' -o -name dropin.cache \) -print0 | $(XARGS) -0 rm
	find . -name _trial_temp\* -type d -print0 | $(XARGS) -0 rm -r

build: check-virtualenv
	-mkdir -p var/log var/tmp
	./bin/check-dependencies
	ant jar
	pip install --download-cache=$$VIRTUAL_ENV/download-cache -r requirements.txt

# Note that build-deployment is only used by our deployment scripts running
# on a fluiddb instance. It should not be invoked by regular humans.
build-deployment:
	-mkdir -p var/log var/tmp
	ant jar
	virtualenv .
	./bin/pip install --download-cache=/var/lib/fluidinfo/source-dependencies -r requirements.txt
	./bin/check-dependencies

build-clean: clean
	rm -rf var

pyflakes:
	@test -f .check-pyflakes || touch -t 197001010000 .check-pyflakes
	find . \( -name _build -o -name var \) -type d -prune -o -name '*.py' -newer .check-pyflakes -print0 | $(XARGS) -0 pyflakes
	find bin -not -name '*~' -newer .check-pyflakes -type f -print0 | $(XARGS) -0 grep -l python | $(XARGS) pyflakes
	@touch .check-pyflakes

pep8: check-virtualenv
	@test -f .check-pep8 || touch -t 197001010000 .check-pep8
	find . \( -name _build -o -name var -o -path ./bin/s3-multipart \) -type d -prune -o -name '*.py' -newer .check-pep8 -print0 | $(XARGS) -0 -n 20 pep8
	find bin -type f -not -path "bin/s3-multipart/*" -not -name '*~' -newer .check-pep8 -print0 | $(XARGS) -0 grep -l python | $(XARGS) -n 20 pep8
	@touch .check-pep8

lint: pep8 pyflakes

etags:
	etags `find . \( -name '*_thrift' -o -name var \) -type d -prune -o -name '*.py' -print`
