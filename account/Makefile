# Makefile.include should set the WEBTOP variable to the location to install to
include Makefile.include

.PHONY: test install

test:
	py.test --pep8 --cov=account

install::
	mkdir -p ${WEBTOP}/account/templates
	cp account/*.py ${WEBTOP}/account/
	cp account/templates/*.html ${WEBTOP}/account/templates/
	echo "import sys; sys.path.insert(0, '${WEBTOP}')" > ${WEBTOP}/account.wsgi
	echo "from account import app as application" >> ${WEBTOP}/account.wsgi
	@echo "Do not edit files in this directory!" > ${WEBTOP}/README
	@echo "Edit the originals and use 'make' to install them here" >> ${WEBTOP}/README
