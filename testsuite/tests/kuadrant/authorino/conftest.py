"""Conftest for Authorino tests"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.api_key import APIKey
from testsuite.policy.authorization.auth_config import AuthConfig
from testsuite.openshift.authorino import AuthorinoCR, Authorino, PreexistingAuthorino


@pytest.fixture(scope="session")
def authorino(authorino, openshift, blame, request, testconfig, label) -> Authorino:
    """Authorino instance"""
    if authorino:
        return authorino

    authorino_config = testconfig["service_protection"]["authorino"]
    if not authorino_config["deploy"]:
        return PreexistingAuthorino(
            authorino_config["auth_url"],
            authorino_config["oidc_url"],
            authorino_config["metrics_service_name"],
        )

    authorino = AuthorinoCR.create_instance(
        openshift,
        image=authorino_config.get("image"),
        log_level=authorino_config.get("log_level"),
        name=blame("authorino"),
        label_selectors=[f"testRun={label}"],
    )
    request.addfinalizer(authorino.delete)
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider, route, authorization_name, openshift, label) -> AuthConfig:
    """In case of Authorino, AuthC onfig used for authorization"""
    if authorization is None:
        authorization = AuthConfig.create_instance(openshift, authorization_name, route, labels={"testRun": label})
    authorization.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def create_api_key(blame, request, openshift):
    """Creates API key Secret"""

    def _create_secret(name, label_selector, api_key, ocp: OpenShiftClient = openshift):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()
