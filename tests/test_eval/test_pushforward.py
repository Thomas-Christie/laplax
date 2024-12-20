"""Tests for `laplax.eval.pushforward`."""

import jax
import jax.numpy as jnp
import pytest_cases

from laplax.curv.cov import create_posterior_function
from laplax.curv.ggn import create_ggn_mv
from laplax.eval.pushforward import set_lin_pushforward, set_mc_pushforward

from .cases.regression import case_regression

DEFAULT_CASE_LIST = [case_regression]
# DEFAULT_CASE_LIST = [case_regression, case_classification]
# # case_classifciation is slow.


@pytest_cases.parametrize(
    "curv_op",
    ["full", "diagonal", "low_rank"],
)
@pytest_cases.parametrize_with_cases("task", cases=DEFAULT_CASE_LIST)
def test_mc_pushforward(curv_op, task):
    model_fn = task.get_model_fn()
    params = task.get_parameters()
    data = task.get_data_batch(batch_size=20)

    # Set get posterior function
    ggn_mv = create_ggn_mv(model_fn, params, data, task.loss_fn_type)
    get_posterior = create_posterior_function(
        curv_op,
        mv=ggn_mv,
        layout=params,
        key=jax.random.key(20),
        maxiter=20,
    )

    # Set pushforward
    pushforward = set_mc_pushforward(
        key=jax.random.key(0),
        model_fn=model_fn,
        mean=params,
        posterior=get_posterior,
        prior_arguments={"prior_prec": 99999999999.0},
        n_weight_samples=100000,
    )

    # Compute pushforwards
    # pushforward = jax.jit(pushforward)
    results = jax.vmap(pushforward)(data["input"])

    # # Check results
    pred = jax.vmap(lambda x: model_fn(params, x))(data["input"])
    assert (5, task.out_channels) == results["samples"].shape[1:]  # Check shape
    assert jnp.all(results["pred_std"] >= 0)
    assert jnp.allclose(pred, results["pred"])


@pytest_cases.parametrize(
    "curv_op",
    ["full", "diagonal", "low_rank"],
)
@pytest_cases.parametrize_with_cases("task", cases=DEFAULT_CASE_LIST)
def test_lin_pushforward(curv_op, task):
    model_fn = task.get_model_fn()
    params = task.get_parameters()
    data = task.get_data_batch(batch_size=20)

    # Set get posterior function
    ggn_mv = create_ggn_mv(model_fn, params, data, task.loss_fn_type)
    get_posterior = create_posterior_function(
        curv_op,
        ggn_mv,
        layout=params,
        key=jax.random.key(20),
        maxiter=20,
    )

    # Set pushforward
    pushforward = set_lin_pushforward(
        key=jax.random.key(0),
        model_fn=model_fn,
        mean=params,
        posterior=get_posterior,
        prior_arguments={"prior_prec": 99999999999.0},
        n_samples=5,  # TODO(2bys): Find a better way of setting this.
    )

    # Compute pushforward
    pushforward = jax.jit(pushforward)
    results = jax.vmap(pushforward)(data["input"])

    # Check results
    pred = jax.vmap(lambda x: model_fn(params, x))(data["input"])
    assert (5, task.out_channels) == results["samples"].shape[
        1:
    ]  # (batch, samples, out)
    jnp.allclose(pred, results["pred"])
    jnp.allclose(pred, results["pred_mean"], rtol=1e-2)
