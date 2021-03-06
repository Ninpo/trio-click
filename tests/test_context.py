# -*- coding: utf-8 -*-
import trio_click as click
import pytest
from contextlib import contextmanager, asynccontextmanager


def test_ensure_context_objects(runner):
    class Foo(object):
        def __init__(self):
            self.title = 'default'

    pass_foo = click.make_pass_decorator(Foo, ensure=True)

    @click.group()
    @pass_foo
    def cli(foo):
        pass

    @cli.command()
    @pass_foo
    def test(foo):
        click.echo(foo.title)

    result = runner.invoke(cli, ['test'])
    assert not result.exception
    assert result.output == 'default\n'


def test_get_context_objects(runner):
    class Foo(object):
        def __init__(self):
            self.title = 'default'

    pass_foo = click.make_pass_decorator(Foo, ensure=True)

    @click.group()
    @click.pass_context
    def cli(ctx):
        ctx.obj = Foo()
        ctx.obj.title = 'test'

    @cli.command()
    @pass_foo
    def test(foo):
        click.echo(foo.title)

    result = runner.invoke(cli, ['test'])
    assert not result.exception
    assert result.output == 'test\n'


def test_get_context_objects_no_ensuring(runner):
    class Foo(object):
        def __init__(self):
            self.title = 'default'

    pass_foo = click.make_pass_decorator(Foo)

    @click.group()
    @click.pass_context
    def cli(ctx):
        ctx.obj = Foo()
        ctx.obj.title = 'test'

    @cli.command()
    @pass_foo
    def test(foo):
        click.echo(foo.title)

    result = runner.invoke(cli, ['test'])
    assert not result.exception
    assert result.output == 'test\n'


def test_get_context_objects_missing(runner):
    class Foo(object):
        pass

    pass_foo = click.make_pass_decorator(Foo)

    @click.group()
    @click.pass_context
    def cli(ctx):
        pass

    @cli.command()
    @pass_foo
    def test(foo):
        click.echo(foo.title)

    result = runner.invoke(cli, ['test'])
    assert result.exception is not None
    assert isinstance(result.exception, RuntimeError)
    assert "Managed to invoke callback without a context object " \
        "of type 'Foo' existing" in str(result.exception)


def test_multi_enter(runner):
    called = []

    @click.command()
    @click.pass_context
    async def cli(ctx):
        def callback():
            called.append(True)
        ctx.call_on_close(callback)

        async with ctx:
            pass
        assert not called

    result = runner.invoke(cli, [])
    if result.exception:
        raise result.exception
    assert called == [True]


def test_global_context_object(runner):
    @click.command()
    @click.pass_context
    def cli(ctx):
        assert click.get_current_context() is ctx
        ctx.obj = 'FOOBAR'
        assert click.get_current_context().obj == 'FOOBAR'

    assert click.get_current_context(silent=True) is None
    runner.invoke(cli, [], catch_exceptions=False)
    assert click.get_current_context(silent=True) is None


def test_context_meta(runner):
    LANG_KEY = __name__ + '.lang'

    def set_language(value):
        click.get_current_context().meta[LANG_KEY] = value

    def get_language():
        return click.get_current_context().meta.get(LANG_KEY, 'en_US')

    @click.command()
    @click.pass_context
    def cli(ctx):
        assert get_language() == 'en_US'
        set_language('de_DE')
        assert get_language() == 'de_DE'

    runner.invoke(cli, [], catch_exceptions=False)


@pytest.mark.anyio
async def test_context_pushing():
    rv = []

    @click.command()
    def cli():
        pass

    ctx = click.Context(cli)

    @ctx.call_on_close
    def test_callback():
        rv.append(42)

    async with ctx.scope(cleanup=False):
        # Internal
        assert ctx._depth == 2

    assert rv == []

    async with ctx.scope():
        # Internal
        assert ctx._depth == 1

    assert rv == [42]


@pytest.mark.anyio
async def test_async_context_mgr():
    @asynccontextmanager
    async def manager():
        val = [1]
        yield val
        val[0] = 0

    @click.command()
    def cli():
        pass

    ctx = click.Context(cli)

    async with ctx.scope():
        rv = await ctx.enter_async_context(manager())
        assert rv[0] == 1, rv

        # Internal
        assert ctx._depth == 1

    assert rv == [0], rv


@pytest.mark.anyio
async def test_context_mgr():
    @contextmanager
    def manager():
        val = [1]
        yield val
        val[0] = 0

    @click.command()
    def cli():
        pass

    ctx = click.Context(cli)

    async with ctx.scope():
        rv = ctx.enter_context(manager())
        assert rv[0] == 1, rv

        # Internal
        assert ctx._depth == 1

    assert rv == [0], rv


def test_pass_obj(runner):
    @click.group()
    @click.pass_context
    def cli(ctx):
        ctx.obj = 'test'

    @cli.command()
    @click.pass_obj
    def test(obj):
        click.echo(obj)

    result = runner.invoke(cli, ['test'])
    assert not result.exception
    assert result.output == 'test\n'


def test_close_before_pop(runner):
    called = []

    @click.command()
    @click.pass_context
    def cli(ctx):
        ctx.obj = 'test'

        @ctx.call_on_close
        def foo():
            assert click.get_current_context().obj == 'test'
            called.append(True)
        click.echo('aha!')

    result = runner.invoke(cli, [])
    assert not result.exception
    assert result.output == 'aha!\n'
    assert called == [True]


def test_make_pass_decorator_args(runner):
    """
    Test to check that make_pass_decorator doesn't consume arguments based on
    invocation order.
    """
    class Foo(object):
        title = 'foocmd'

    pass_foo = click.make_pass_decorator(Foo)

    @click.group()
    @click.pass_context
    def cli(ctx):
        ctx.obj = Foo()

    @cli.command()
    @click.pass_context
    @pass_foo
    def test1(foo, ctx):
        click.echo(foo.title)

    @cli.command()
    @pass_foo
    @click.pass_context
    def test2(ctx, foo):
        click.echo(foo.title)

    result = runner.invoke(cli, ['test1'])
    assert not result.exception
    assert result.output == 'foocmd\n'

    result = runner.invoke(cli, ['test2'])
    assert not result.exception
    assert result.output == 'foocmd\n'


@pytest.mark.trio
async def test_exit_not_standalone():
    @click.command()
    @click.pass_context
    def cli(ctx):
        ctx.exit(1)

    assert await cli.main([], 'test_exit_not_standalone', standalone_mode=False) == 1

    @click.command()
    @click.pass_context
    def cli(ctx):
        ctx.exit(0)

    assert await cli.main([], 'test_exit_not_standalone', standalone_mode=False) == 0
