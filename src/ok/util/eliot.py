from functools import partial, wraps
from inspect import getcallargs, iscoroutinefunction

from eliot import start_action


def log_call(wrapped_function=None, action_type=None, include_args=None, include_result=True):
    """
    A version of the `eliot.log_call` decorator that works with async functions.
    See <https://github.com/itamarst/eliot/issues/393>.

    ---

    Decorator/decorator factory that logs inputs and the return result.

    If used with inputs (i.e. as a decorator factory), it accepts the following
    parameters:

    @param action_type: The action type to use.  If not given the function name
        will be used.
    @param include_args: If given, should be a list of strings, the arguments to log.
    @param include_result: True by default. If False, the return result isn't logged.
    """
    if wrapped_function is None:
        return partial(
            log_call,
            action_type=action_type,
            include_args=include_args,
            include_result=include_result,
        )

    if action_type is None:
        action_type = "{}.{}".format(wrapped_function.__module__, wrapped_function.__qualname__)

    if include_args is not None:
        from inspect import signature

        sig = signature(wrapped_function)
        if set(include_args) - set(sig.parameters):
            raise ValueError(("include_args ({}) lists arguments not in the wrapped function").format(include_args))

    @wraps(wrapped_function)
    def logging_wrapper(*args, **kwargs):
        callargs = getcallargs(wrapped_function, *args, **kwargs)

        # Remove self is it's included:
        if "self" in callargs:
            callargs.pop("self")

        # Filter arguments to log, if necessary:
        if include_args is not None:
            callargs = {k: callargs[k] for k in include_args}

        with start_action(action_type=action_type, **callargs) as ctx:
            result = wrapped_function(*args, **kwargs)
            if include_result:
                ctx.add_success_fields(result=result)
            return result

    @wraps(wrapped_function)
    async def async_logging_wrapper(*args, **kwargs):
        callargs = getcallargs(wrapped_function, *args, **kwargs)

        # Remove self is it's included:
        if "self" in callargs:
            callargs.pop("self")

        # Filter arguments to log, if necessary:
        if include_args is not None:
            callargs = {k: callargs[k] for k in include_args}

        with start_action(action_type=action_type, **callargs) as ctx:
            result = await wrapped_function(*args, **kwargs)
            if include_result:
                ctx.add_success_fields(result=result)
            return result

    if iscoroutinefunction(wrapped_function):
        return async_logging_wrapper
    return logging_wrapper
