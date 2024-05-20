from fabric import Connection,Result
from pathlib import PurePosixPath
from io import StringIO
import uuid
import logging
import typing
from datetime import datetime
from ipaddress import IPv4Address,IPv4Network

from p4_command_controller.p4_switch import P4Switch, table_entry_params
from p4_command_controller.mac_address import MacAddress

SDE=PurePosixPath("/root/bf-sde-9.1.0")
SDE_INSTALL=SDE/'install'
SDE_BIN=SDE_INSTALL/"bin"
CODE_PATH = PurePosixPath("/root/bfrt_code_dir")

tofino_env={str(k):str(v) for k,v in dict(SDE=SDE,SDE_INSTALL=SDE_INSTALL)}

def _entry_params_to_string(x:table_entry_params) -> str:
    r = []
    for k,v in x.items():
        if isinstance(v,IPv4Network):
            code=f"{k}={hex(int(v.network_address))},\n{k}_p_length={v.prefixlen}"
        else:
            if isinstance(v,IPv4Address):
                v=hex(int(v))
            elif isinstance(v,MacAddress):
                v=hex(v.value)
            code=f"{k}={v}"
        r.append(code)
    return ',\n'.join(r)

def _make_code(
        table: str, 
        match_params: table_entry_params, 
        action: str, 
        action_params: table_entry_params = {}
    ) -> str:
    match_s = _entry_params_to_string(match_params)
    code = f"""
# {datetime.now().isoformat()}
table=bfrt.srv6.pipe.Ingress.{table}
try:
    table.delete(
        {match_s}
    )
except:
    pass
table.add_with_{action}(
    {match_s},
    {_entry_params_to_string(action_params)}
)
# table.dump()
    """
    return code

@typing.final
class Tofino(P4Switch):
    def __init__(self,ssh_ip:str,ssh_port:int,user:str,password:str,logger:typing.Optional[logging.Logger]=None,connect_immediately:bool=True) -> None:
        self.logger = logger if isinstance(logger,logging.Logger) else logging.getLogger("Simple Switch Cli")
        self._lifespan = self._make_lifespan(ssh_ip,ssh_port,user,password)
        if connect_immediately:
            self.connection = next(self._lifespan)
    
    def connect(self):
        if not getattr(self,'connection',None):
            self.connection = next(self._lifespan)

    def _make_lifespan(self,ip:str,port:int,user:str,password:str) -> typing.Generator[Connection, None, None]:
        with Connection(
            host = ip,
            port = port,
            user = user,
            connect_kwargs=dict(password=password)
        ) as conn:
            yield conn 
        self.logger.info("p4 runtime cli 已经关闭。")
    
    def set_register(self, name: str, *, index: int | None = None, value: int):
        raise Exception("尚未实现tofino设置register")
    def reset_register(self, name: str):
        raise Exception("尚未实现tofino设置register")

    def update_table_entry(self, 
                           table: str, 
                           match_params: table_entry_params, 
                           action: str, 
                           action_params: table_entry_params = {}
                          ) -> None:
        code=_make_code(table,match_params,action,action_params)
        self.send_code(code)

    def send_code(self,code:str,is_delete=True) -> None:
        c = self.connection
        code_file_path = CODE_PATH/f"{uuid.uuid4()}.py"
        c.put(StringIO(code),str(code_file_path))
        result:Result = c.run(f'bash /root/bf-sde-9.1.0/run_bfshell.sh -b {code_file_path}',env=tofino_env,timeout=60,hide=True)
        if len(result.stderr)>0:
            raise Exception(f"命令运行报错:\n{result.stdout}")
        self.logger.info(result.stdout)
        if is_delete:
            c.run(f"rm {code_file_path}")