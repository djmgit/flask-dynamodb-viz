
from typing import List, Any, Optional
from pydantic import BaseModel
from flask import Flask

class DDBTableInterface:
    def scan(*args, **kwargs):
        raise NotImplementedError("Method not implemented")

    def scan(*args, **kwargs):
        raise NotImplementedError("Method not implemented")

class DDBResourceInterface:
    class Table:
        name: str

    class Tables:
        def all():
            pass
    
    tables: Tables


class FlaskDDBVizConfig(BaseModel):
    ddb_resource: Any
    allowed_tables: Optional[List[str]] = None

def _big_scan(table: DDBTableInterface):
        scan_result = []
        last_evaluated_key = None

        while True:
            if last_evaluated_key is None:
                scanned_page = table.scan()
            else:
                scanned_page = table.scan(ExclusiveStartKey=last_evaluated_key)

            if scanned_page.get("Items") and len(scanned_page["Items"]) > 0:
                scan_result.extend(scanned_page["Items"])

            if "LastEvaluatedKey" not in scanned_page:
                break

            last_evaluated_key = scanned_page["LastEvaluatedKey"]

        return scan_result

def _get_all(table: DDBTableInterface):
    return _big_scan(table)

#def _get_table_from_factory(table_name: str, ddb_table_factory: DDBTableFactory) -> TableConfig:
    #return list(filter(lambda table_config: table_config.table_name == table_name, ddb_table_factory.tables))[0]

def _show_table_view(table_name: str, flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_resource: DDBResourceInterface = flask_ddb_viz_config.ddb_resource
    ddb_tables: List[DDBResourceInterface.Table] = ddb_resource.tables.all()
    table_names = [table.name for table in ddb_tables]
    if table_name not in table_names:
        return {"error": "Table does not exist"}, 404
    allowed_tables = flask_ddb_viz_config.allowed_tables
    if allowed_tables and table_name not in allowed_tables:
        return {"error": "Table cannot be shown"}, 403
    ddb_table: DDBTableInterface = ddb_resource.Table(table_name)
    resultset = _get_all(ddb_table)
    return {"table_name": table_name, "items": resultset}, 200

def _list_tables(flask_ddb_viz_config: FlaskDDBVizConfig):
    ddb_resource: DDBResourceInterface = flask_ddb_viz_config.ddb_resource
    ddb_tables: List[DDBResourceInterface.Table] = ddb_resource.tables.all()
    tables_names = [table.name for table in ddb_tables]
    allowed_tables = flask_ddb_viz_config.allowed_tables
    ddb_tables = ddb_tables if not allowed_tables else list(filter(lambda table: table in allowed_tables, ddb_tables))

    return {"items_count": len(tables_names), "tables": tables_names}, 200
   

class FlaskDDBViz:
    
    def __init__(self, app: Optional[Flask]):
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        flask_ddb_viz_config: FlaskDDBVizConfig = app.config["FLASK_DDB_VIZ_CONFIG"]

        def show_table_view_wrapper(table_name: str):
            return _show_table_view(table_name, flask_ddb_viz_config)
        def list_tables_wrapper():
            return _list_tables(flask_ddb_viz_config)
        app.add_url_rule("/ddb_table/<table_name>/records", view_func=show_table_view_wrapper, methods=["GET"])
        app.add_url_rule("/ddb_tables/list", view_func=list_tables_wrapper, methods=["GET"])
    

