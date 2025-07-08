from qtpy import QtCore


class QtExtension(QtCore.QObject):
    """
    Base class for Qt extensions.
    """

    def __init__(self, qt_window, app):
        self.app = qt_window

    def run(self):
        """
        Run the extension.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def stop(self):
        """
        Stop the extension.
        """
        raise NotImplementedError("Subclasses must implement this method.")
