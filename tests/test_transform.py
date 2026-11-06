from core.transform import (
    AutoYieldBase,
    AutoYieldMeta,
    AutoYieldMethodBase,
    auto_yield_class,
    register_auto_yield,
)


@register_auto_yield
def other_func(self, x):
    if x > 0:
        self.x = x
        yield x
        yield x + 1
        self.x = x + 1
    else:
        return x


def another_func(x):
    # Returns a normal value.
    return x * 2


@register_auto_yield
def foo():
    yield 2
    return 3


class A:
    @register_auto_yield
    def a(self):
        yield 1


def test_decorator():
    @auto_yield_class(debug=True)
    class MyClass:
        def my_method_1(self):
            self.x = 0
            other_func(self, 1)

        def my_method_2(self):
            self.x = another_func(4)

        def my_method_3(self):
            self.x = foo()

    @auto_yield_class
    class MyClass2(MyClass):
        def my_method_2(self):
            super().my_method_2()

    instance = MyClass()
    assert list(instance.my_method_1()) == [1, 2]
    assert instance.x == 2
    instance.my_method_3()
    assert instance.x == 2

    instance = MyClass2()
    instance.my_method_2()
    assert instance.x == 8

    @auto_yield_class(debug=True)
    class MyClass:
        def my_method(self):
            other_func(self, 1)
            another_func(2)
            A().a()

    instance = MyClass()
    assert list(instance.my_method()) == [1, 2, 1]


def test_base_class():
    class Foo(AutoYieldBase, debug=True):
        def foo(self):
            self.x = another_func(2)

    instance = Foo()
    instance.foo()
    assert instance.x == 4

    class Bar(Foo, debug=True):
        def foo(self):
            super().foo()

        def bar(self):
            self.x = another_func(3)

        def shi(self):
            self.x = foo()

    instance = Bar()
    instance.foo()
    assert instance.x == 4
    instance.bar()
    assert instance.x == 6
    list(instance.shi())
    assert instance.x == 3


def test_meta_class():
    class Foo(metaclass=AutoYieldMeta, debug=True):
        def foo(self):
            other_func(self, 2)

    instance = Foo()
    assert list(instance.foo()) == [2, 3]
    assert instance.x == 3

    class Bar(Foo, debug=True):
        def foo(self):
            yield from super().foo()

        def bar(self):
            self.x = another_func(3)

        def go(self):
            other_func(self, 4)

    instance = Bar()
    assert list(instance.foo()) == [2, 3]
    instance.bar()
    assert instance.x == 6
    assert list(instance.go()) == [4, 5]


def test_method_meta_class():
    class Foo(AutoYieldMethodBase, debug=True):
        def foobar(self):
            other_func(self, 2)

    instance = Foo()
    assert list(instance.foobar()) == [2, 3]
    assert instance.x == 3

    class Bar(Foo, debug=True):
        def foobar(self):
            yield from super().foobar()

        def bar(self):
            self.x = another_func(3)

        def go(self):
            other_func(self, 4)

    instance = Bar()
    assert list(instance.foobar()) == [2, 3]
    instance.bar()
    assert instance.x == 6
    assert list(instance.go()) == [4, 5]
