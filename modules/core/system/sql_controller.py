from core.decorators import instance, command
from core.command_param_types import Any, Const
from core.chat_blob import ChatBlob
import json


@instance()
class SqlController:
    def inject(self, registry):
        self.bot = registry.get_instance("bot")
        self.db = registry.get_instance("db")
        self.text = registry.get_instance("text")
        self.command_alias_service = registry.get_instance("command_alias_service")
        self.getresp = registry.get_instance("translation_service").get_response

    def start(self):
        self.command_alias_service.add_alias("querysql", "sql query")
        self.command_alias_service.add_alias("executesql", "sql exec")

    @command(command="sql", params=[Const("query"), Any("sql_statement")], access_level="superadmin",
             description="Execute a SQL query and return the results")
    def sql_query_cmd(self, request, _, sql):
        try:
            results = self.db.query(sql)
            return ChatBlob(self.getresp("module/system", "sql_blob_title", {"count": len(results)}),
                            json.dumps(results, indent=4, sort_keys=True))
        except Exception as e:
            return self.getresp("module/system", "sql_fail", {"error": str(e)})

    @command(command="sql", params=[Const("exec"), Any("sql_statement")], access_level="superadmin",
             description="Execute a SQL query and return number of affected rows")
    def sql_exec_cmd(self, request, _, sql):
        try:
            row_count = self.db.exec(sql)
            return self.getresp("module/system", "sql_exec_success", {"count": row_count})
        except Exception as e:
            return self.getresp("module/system", "sql_fail", {"error": str(e)})

    @command(command="sql", params=[Const("files")], access_level="superadmin",
             description="Show SQL files that have been loaded")
    def sql_files_cmd(self, request, _):
        data = self.db.query("SELECT file, version FROM db_version ORDER BY file ASC")

        blob = ""
        for row in data:
            reload_link = ""
            if row.file != "db_version":
                reload_link = self.text.make_tellcmd("Reload", f"sql load {row.file}")
            blob += f"{row.file} - {row.version} {reload_link}\n"

        return ChatBlob("SQL Files (%d)" % len(data), blob)

    @command(command="sql", params=[Const("load"), Any("sql_file")], access_level="superadmin",
             description="Load or reload a SQL file")
    def sql_load_cmd(self, request, _, file):
        try:
            self.db.load_sql_file(file, force_update=True)
            return f"SQL file <highlight>{file}</highlight> has been loaded."
        except Exception as e:
            return self.getresp("module/system", "sql_fail", {"error": str(e)})
