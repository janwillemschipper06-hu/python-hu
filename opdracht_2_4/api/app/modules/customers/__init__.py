"""Customers module — read-only lookup over the external ``ext.Customer`` table.

Layers: :mod:`~app.modules.customers.schemas` (API models),
:mod:`~app.modules.customers.repository` (stored-procedure call),
:mod:`~app.modules.customers.service` (orchestration), and
:mod:`~app.modules.customers.router` (the portal HTTP endpoint). The portal owns
no customer data (``docs/adr/0013``): a Project stores only the ``CustomerConfigID``.
"""
