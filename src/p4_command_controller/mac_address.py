from pydantic_extra_types.mac_address import MacAddress as pydantic_MacAddress
from pydantic import TypeAdapter
from netaddr import EUI
import typing

@typing.final
class MacAddress(pydantic_MacAddress):
    def __init__(self,value) -> None:
        TypeAdapter(pydantic_MacAddress).validate_python(value)
        self._mac_obj = EUI(value)

    def __getattr__(self,attr):
        return getattr(self._mac_obj, attr)