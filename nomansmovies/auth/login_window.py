"""Login / Signup dialog. On success, persists session and emits authed signal."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QWidget, QMessageBox
)

from ..supabase_client import supabase, save_session


class _LoginPage(QWidget):
    request_signup = Signal()
    success = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(12)
        title = QLabel("Welcome back")
        title.setStyleSheet("font-size: 22pt; font-weight: 700;")
        lay.addWidget(title)
        lay.addWidget(QLabel("Sign in to NoMansMovies"))

        self.email = QLineEdit(); self.email.setPlaceholderText("email")
        self.password = QLineEdit(); self.password.setPlaceholderText("password"); self.password.setEchoMode(QLineEdit.Password)
        lay.addSpacing(8)
        lay.addWidget(self.email)
        lay.addWidget(self.password)

        self.btn = QPushButton("Log in")
        self.btn.setProperty("accent", True); self.btn.style().unpolish(self.btn); self.btn.style().polish(self.btn)
        self.btn.clicked.connect(self._login)
        lay.addWidget(self.btn)

        switch = QPushButton("No account?  Create one")
        switch.setFlat(True)
        switch.clicked.connect(self.request_signup.emit)
        lay.addWidget(switch)
        lay.addStretch(1)

    def _login(self) -> None:
        e, p = self.email.text().strip(), self.password.text()
        if not e or not p:
            QMessageBox.warning(self, "Missing", "Enter email and password."); return
        try:
            res = supabase().auth.sign_in_with_password({"email": e, "password": p})
        except Exception as ex:
            QMessageBox.critical(self, "Login failed", str(ex)); return
        if not res or not res.session:
            QMessageBox.critical(self, "Login failed", "Invalid credentials."); return
        save_session(res.session.access_token, res.session.refresh_token)
        self.success.emit()


class _SignupPage(QWidget):
    request_login = Signal()
    success = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(12)
        title = QLabel("Create your account")
        title.setStyleSheet("font-size: 22pt; font-weight: 700;")
        lay.addWidget(title)
        lay.addWidget(QLabel("Pick a username and password"))

        self.username = QLineEdit(); self.username.setPlaceholderText("username")
        self.email = QLineEdit(); self.email.setPlaceholderText("email")
        self.password = QLineEdit(); self.password.setPlaceholderText("password (min 6)"); self.password.setEchoMode(QLineEdit.Password)
        lay.addSpacing(8)
        lay.addWidget(self.username)
        lay.addWidget(self.email)
        lay.addWidget(self.password)

        self.btn = QPushButton("Sign up")
        self.btn.setProperty("accent", True); self.btn.style().unpolish(self.btn); self.btn.style().polish(self.btn)
        self.btn.clicked.connect(self._signup)
        lay.addWidget(self.btn)

        switch = QPushButton("Already have an account?  Log in")
        switch.setFlat(True)
        switch.clicked.connect(self.request_login.emit)
        lay.addWidget(switch)
        lay.addStretch(1)

    def _signup(self) -> None:
        u, e, p = self.username.text().strip(), self.email.text().strip(), self.password.text()
        if not u or not e or len(p) < 6:
            QMessageBox.warning(self, "Missing", "Username, email, and a 6+ char password are required."); return
        try:
            res = supabase().auth.sign_up({
                "email": e,
                "password": p,
                "options": {"data": {"username": u}},
            })
        except Exception as ex:
            QMessageBox.critical(self, "Signup failed", str(ex)); return
        if not res:
            QMessageBox.critical(self, "Signup failed", "Could not create account."); return
        # If email confirmation is required, session may be None — fall back to login attempt.
        if res.session:
            save_session(res.session.access_token, res.session.refresh_token)
            self.success.emit()
        else:
            QMessageBox.information(
                self, "Check your email",
                "We sent a confirmation link. Confirm and log in.")
            self.request_login.emit()


class AuthDialog(QDialog):
    authed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NoMansMovies")
        self.setModal(True)
        self.setMinimumSize(420, 520)

        self.stack = QStackedWidget(self)
        self.login_page = _LoginPage()
        self.signup_page = _SignupPage()
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.signup_page)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        self.login_page.request_signup.connect(lambda: self.stack.setCurrentIndex(1))
        self.signup_page.request_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.login_page.success.connect(self._done)
        self.signup_page.success.connect(self._done)

    def _done(self) -> None:
        self.authed.emit()
        self.accept()
