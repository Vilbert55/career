"""Заготовка тестов под новый код. Скопировать, переименовать в test_<модуль>.py, заполнить.

Чек-лист случаев: основной сценарий; границы (0, 1, пусто, ровно на лимите, +-1);
некорректный вход (какое исключение); деньги и округление; состояние (повтор, порядок,
неудачная операция ничего не меняет); несколько пользователей; время через часы.
"""
import pytest

# from my_module import MyService, MyError


@pytest.fixture
def svc(clock):
    # return MyService(clock=clock)
    pytest.skip("заготовка: заменить на свой сервис")


def test_happy_path(svc):
    ...


@pytest.mark.parametrize(("value", "expected"), [])
def test_boundaries(svc, value, expected):
    ...


def test_invalid_input_raises(svc):
    # with pytest.raises(MyError, match="..."):
    #     svc.do(...)
    ...


def test_failed_operation_changes_nothing(svc):
    ...
