
import connexion

from storage.openapi_app import encoder

def create_openapi_application():
    app = connexion.App(__name__, specification_dir='./openapi_app/openapi/')
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api('openapi.yaml',
                arguments={'title': 'Storage API'},
                pythonic_params=True)
    return app.app
