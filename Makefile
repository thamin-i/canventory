PATH_SOURCES=app
PATH_HOOKS=.hooks
PATH_VENV=.venv
PYTHON_VERSION=3.13

.PHONY: install

install: _setup_local _install_hooks

uninstall: _uninstall_hooks _remove_venv

_install_hooks:
	${PATH_HOOKS}/install_hooks.sh -i

_uninstall_hooks:
	${PATH_HOOKS}/install_hooks.sh -u all

_setup_local:
	python${PYTHON_VERSION} -m venv .venv
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m pip install --upgrade pip
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m pip install -r requirements-dev.txt
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m pip install -r requirements.txt

_remove_venv:
	rm -rf .venv

lint:
	export PYTHONPATH="${PYTHONPATH}:$$(pwd)/${PATH_SOURCES}" && ${PATH_VENV}/bin/python${PYTHON_VERSION} -m pylint --rcfile ./setup.cfg ${PATH_SOURCES}

mypy:
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m mypy ${PATH_SOURCES} --ignore-missing-imports --strict --implicit-reexport --config-file ./setup.cfg

black:
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m black ${PATH_SOURCES} --check --line-length 80

flake:
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m flake8 ${PATH_SOURCES} --config ./setup.cfg

isort:
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m isort ${PATH_SOURCES} --check-only --settings-path ./setup.cfg

format:
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m black ${PATH_SOURCES} --line-length 80
	${PATH_VENV}/bin/python${PYTHON_VERSION} -m isort ${PATH_SOURCES} --settings-path ./setup.cfg

check: black isort mypy flake lint
