"""Execution adapters. The strategy never knows which one it's talking to —
that's what lets us paper-test, then go live, with the same code."""


class PaperBroker:
    """Simulated fills. Applies slippage so paper results aren't flattering."""

    def __init__(self, slippage_bps=5):
        self.s = slippage_bps / 10000.0

    def buy_price(self, price):
        return price * (1 + self.s)

    def sell_price(self, price):
        return price * (1 - self.s)


class RobinhoodBroker:
    """Go-live execution adapter. Wraps the robinhood-trading MCP
    `place_equity_order` tool against the Agentic cash account.
    Intentionally unimplemented during the paper phase — wire it up only
    after a strategy clears the graduation bar."""

    def __init__(self, account_number):
        self.account = account_number

    def buy_price(self, price):
        raise NotImplementedError("Wire to place_equity_order before going live")

    def sell_price(self, price):
        raise NotImplementedError("Wire to place_equity_order before going live")
