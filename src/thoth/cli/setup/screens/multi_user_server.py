"""Multi-user server configuration screen for setup wizard.

Shown to admins setting up a shared Thoth server where multiple users
will connect. Configures THOTH_MULTI_USER, THOTH_VAULTS_ROOT, and
self-registration policy, then creates the first admin user.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from .base import BaseScreen


class MultiUserServerScreen(BaseScreen):
    """Wizard screen for configuring a multi-user Thoth server."""

    def __init__(self) -> None:
        """Initialize multi-user server configuration screen."""
        super().__init__(
            title='Multi-User Server Setup',
            subtitle='Configure shared server for multiple users',
        )
        self.vaults_root: str = '/vaults'
        self.allow_registration: bool = False
        self.admin_username: str = ''
        self.created_token: str | None = None

    def compose_content(self) -> ComposeResult:
        """Compose multi-user server setup content."""
        yield Static(
            'Set up Thoth as a shared server so multiple users can connect '
            'with their own isolated vaults and Letta agents.\n\n'
            'Each user will receive a unique API token to use in their '
            'Obsidian plugin settings.',
            classes='help-text',
        )

        with Vertical(classes='form-section'):
            yield Label('Vaults Root Directory', classes='field-label')
            yield Label(
                'Where user vault directories will be created on this server '
                '(e.g. /vaults → /vaults/alice, /vaults/bob)',
                classes='field-description',
            )
            yield Input(
                value=self.vaults_root,
                placeholder='/vaults',
                id='vaults-root-input',
            )

        with Vertical(classes='form-section'):
            yield Label('Self-Registration', classes='field-label')
            yield Label(
                'Allow users to register themselves via POST /auth/register, '
                'or require admin to create all accounts via CLI.',
                classes='field-description',
            )
            with RadioSet(id='registration-radio'):
                yield RadioButton(
                    'Admin creates accounts (recommended)', value=True, id='reg-admin'
                )
                yield RadioButton('Allow self-registration', id='reg-self')

        with Vertical(classes='form-section'):
            yield Label('Admin Username', classes='field-label')
            yield Label(
                'Create the first admin account. Save the token that is shown '
                'after setup — it grants admin access.',
                classes='field-description',
            )
            yield Input(
                placeholder='admin',
                id='admin-username-input',
            )

        if self.created_token:
            yield Static(
                f'✓ Admin user created.\n\n'
                f'API Token (save this now):\n{self.created_token}',
                id='token-display',
                classes='success-box',
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == 'next':
            self._handle_next()
        elif event.button.id == 'back':
            self.app.pop_screen()

    def _handle_next(self) -> None:
        """Validate and proceed."""
        vaults_input = self.query_one('#vaults-root-input', Input)
        self.vaults_root = vaults_input.value.strip() or '/vaults'

        admin_input = self.query_one('#admin-username-input', Input)
        self.admin_username = admin_input.value.strip()

        reg_radio = self.query_one('#registration-radio', RadioSet)
        self.allow_registration = reg_radio.pressed_index == 1

        if not self.admin_username:
            self.show_error('Admin username is required.')
            return

        if len(self.admin_username) < 3:
            self.show_error('Admin username must be at least 3 characters.')
            return

        asyncio.get_event_loop().run_until_complete(self._create_admin())

    async def _create_admin(self) -> None:
        """Create admin user and display token."""
        try:
            from thoth.auth.service import AuthService

            database_url = os.getenv(
                'DATABASE_URL',
                'postgresql://thoth:thoth_password@localhost:5432/thoth',
            )

            import asyncpg

            conn = await asyncpg.connect(database_url)

            class _Pg:
                def __init__(self, c):
                    self._c = c

                async def fetchrow(self, q, *a):
                    return await self._c.fetchrow(q, *a)

                async def fetch(self, q, *a):
                    return await self._c.fetch(q, *a)

                async def execute(self, q, *a):
                    return await self._c.execute(q, *a)

            auth = AuthService(postgres=_Pg(conn))

            existing = await auth.get_user_by_username(self.admin_username)
            if existing:
                await conn.close()
                self.show_error(
                    f"Username '{self.admin_username}' already exists. "
                    'Choose a different name.'
                )
                return

            user = await auth.create_user(username=self.admin_username, is_admin=True)
            self.created_token = user.api_token

            # Provision vault directory
            vaults_root = Path(self.vaults_root)
            try:
                from thoth.services.vault_provisioner import VaultProvisioner

                provisioner = VaultProvisioner()
                await provisioner.provision_vault(user.username, vaults_root)
            except Exception as e:
                logger.warning(f'Could not provision vault: {e}')

            await conn.close()

            # Update display and emit result
            self.refresh()
            self.dismiss(
                {
                    'vaults_root': self.vaults_root,
                    'allow_registration': self.allow_registration,
                    'admin_username': self.admin_username,
                    'admin_token': self.created_token,
                }
            )

        except Exception as e:
            logger.error(f'Failed to create admin user: {e}')
            self.show_error(f'Failed to create admin user: {e}')
