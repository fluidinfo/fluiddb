import os

from jinja2 import Environment, FileSystemLoader

# Import the various web service resources to cause the API registry to be
# populated as a side-effect.
import fluiddb.web.about
import fluiddb.web.namespaces
import fluiddb.web.objects
import fluiddb.web.permissions
import fluiddb.web.tags
import fluiddb.web.users
import fluiddb.web.values
import fluiddb.web.recent
from fluiddb.doc.api.http.registry import registry
from fluiddb.doc.permissions import permissionsInfo

# Kill a kitten to keep pyflakes quiet about the unused import of fluiddb.
_ = fluiddb


def buildAPIDocumentation(templatePath, outputPath):
    """Build API documentation.

    @param templatePath: The path where the Sphinx templates are located.
    @param outputPath: The path to the directory where generated API
        documentation should be written.
    """
    environment = Environment(loader=FileSystemLoader(templatePath))

    apiAdminOutputPath = os.path.join(outputPath, 'api_admin.html')
    stream = renderAPITemplate(environment, True)
    stream.dump(apiAdminOutputPath)

    apiOutputPath = os.path.join(outputPath, 'api.html')
    stream = renderAPITemplate(environment, False)
    stream.dump(apiOutputPath)

    permissionsOutputPath = os.path.join(outputPath, 'permissions.html')
    stream = renderPermissionsTemplate(environment)
    stream.dump(permissionsOutputPath)


def render(environment, filename, context):
    """Populate a template file with data rendered from the context.

    @param filename: A C{str} with the path to a Jinja2 template.
    @param context: A C{dict} with all the data needed by the template.
    """
    template = environment.get_template(filename)
    rendered = template.stream(**context)
    return rendered


def renderPermissionsTemplate(environment):
    """Render the permissions template.

    @param environment: A Jinja2 C{Environment} instance.
    @return: The rendered template as a C{str}.
    """
    return render(environment, 'permissions.tpl', {'info': permissionsInfo})


def renderAPITemplate(environment, showAdmin):
    """Render the API template.

    This pulls the entire registry and renders it using a Jinja2 template.

    @param environment: A Jinja2 C{Environment} instance.
    @param showAdmin: A C{bool} telling whether we render the admin API for
        managing users.
    @return: The rendered template as a C{str}.
    """
    apis = registry.get(showAdmin=showAdmin)
    return render(environment, 'api.tpl', {'apis': apis,
                                           'showAdmin': showAdmin})
