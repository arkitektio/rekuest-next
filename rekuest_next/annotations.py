from typing import Generic, TypeVar

T = TypeVar("T")


class WithAssignWidget(Generic[T]):

    def __init__(self, widget):
        self.widget = widget

    def get_assign_widget(self):
        return self.widget


class WithReturnWidget(Generic[T]):

    def __init__(self, widget):
        self.widget = widget

    def get_return_widget(self):
        return self.widget
