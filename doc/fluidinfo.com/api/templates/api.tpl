<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="{{ LANGUAGE_CODE }}" xml:lang="{{ LANGUAGE_CODE }}" {% if LANGUAGE_BIDI %}dir="rtl"{% endif %}>
<head>
<title>{% block title %}Fluidinfo API{% endblock %}</title>
<link rel="stylesheet" type="text/css" href="{% block stylesheet %}../css/api.css{% endblock %}" />
{% block extrastyle %}{% endblock %}
{% block extrahead %}{% endblock %}
{% block blockbots %}<meta name="robots" content="NONE,NOARCHIVE" />{% endblock %}
</head>

{#
{% macro httpHeaderWrap(what) -%}
<span class="httpHeader">{{what}}</span>
{%- endmacro %}

{% set acceptEncoding = httpHeaderWrap('Accept-Encoding') %}
{% set contentEncoding = httpHeaderWrap('Content-Encoding') %}
#}

<body>
  <a name="top"></a>
  <div class="document">
    <div class="documentwrapper">
      <div class="bodywrapper">
        <div class="body">


<div class="intro">
  <h1>Fluidinfo API Reference</h1>
  <p>
    On this page you will find detailed information about all
    Fluidinfo HTTP methods. <em>Please note:</em> The example API
    calls and responses shown below are currently only syntactically
    correct examples. The tags used are not guaranteed to exist (we
    plan to change that).  A description of the functionality of the
    HTTP API in general can be found
    <a href="http://doc.fluidinfo.com/fluidDB/api/http.html">here</a>.
    Typographic conventions used on this page are listed
    <a href="#typographic">at bottom</a>.
  </p>
  <p>
    Here is the full set of HTTP API endpoints and all the methods for
    each:
  </p>
  {% if errors %}
  <div class="error">
  <h1>Oops!</h1>
  <p>{{ errors }}</p>
  </div>
  {% endif %}
</div>

<div class="api">
<!-- TOPLEVEL/VERB SUMMARY -->
<table class="summary">
{% for toplevel, verbs in apis %}
    <tr>
    <td class="summary">
    <a href="#{{ toplevel }}">
      <span class="URI">/{{ toplevel }}</span></a>:
    </td>
    <td class="summary">
    {% for verb, func in verbs %}
        <a href="#{{ toplevel }}_{{ verb }}">
          <span class="tt">{{ verb }}</span></a>{% if loop.last %}.{% else %},{% endif %}
    {% endfor %}
    </td>
    <tr/>
{% endfor %}
</table>
<!-- END TOPLEVEL/VERB SUMMARY -->

<!-- FOR TOPLEVEL/VERB -->
{% for toplevel, verbs in apis %}
    <div class="toplevel">
    <hr>
    <a name="{{ toplevel }}"></a>
    <h1>{{ toplevel|capitalize }}</h1>
    <!-- VERB/FUNC LOOP FOR THIS TOPLEVEL -->
    {% for verb, func in verbs %}
        <div class="func">
        <a name="{{ toplevel }}_{{ verb }}"></a>

        <h2>{{ verb }}</h2>
        <div class="toplink"><a class="permalink" href="#{{ toplevel }}_{{ verb }}" title="Link to {{ toplevel }}/{{ verb }}">link</a>|<a href="#top">top</a></div>
        {% if func.adminOnly %}
          <p>
             <span class="adminOnly">
                 {{ verb }} is only useful to administrators.
             </span
          </p>
        {% endif %}
        {% if not func.implemented %}
          <p>
             <span class="unimplemented">
                 {{ verb }} is not yet implemented.
             </span
          </p>
        {% endif %}
        {% if func.description != None %}
            <p> {{ func.description }} </p>
        {% endif %}

        <!-- NOTES FOR THIS FUNC -->
        {% if func.notes %}
            <div class="notes">
            <h2>Note{% if func.notes|length > 1 %}s{% endif %}:</h2>
            <ol>
            {% for note in func.notes %}
                <li><span class="note">{{ note.description }}</span></li>
            {% endfor %}
            </ol>
            </div>
        {% endif %}
        <!-- END FUNC NOTES -->

        <!-- IF USAGES FOR THIS FUNC -->
        {% if func.usages %}
            <div class="usages">
            <!-- USAGE LOOP FOR THIS FUNC -->
            {% for usage in func.usages %}
                <div class="usageHead">
                    {% for subURI in usage.subURIs %}
                        {{ verb }} /{{ toplevel }}{{ subURI }}
                        {% if not loop.last %} <br/> {% endif %}
                    {% endfor %}
                </div>
                <div class="usage">
                    {% if usage.adminOnly %}
                      <p><span class="adminOnly">
                          This URI is only useful to administrators.
                      </span></p>
                    {% endif %}
                    {% if not usage.implemented %}
                      <p><span class="unimplemented">
                             This URI is not yet implemented.
                      </span></p>
                    {% endif %}
                    <p>{{ usage.description }}</p>

                    <!-- ARGUMENTS FOR THIS USAGE -->
                    {% if usage.arguments %}
                        <h3>URI arguments:</h3>
                        <table>
                        <tr><th>Name</th>
                            <th>Type</th>
                            <th>Default</th>
                            <th>Mandatory</th>
                            <th>Description</th></tr>
                        {% for argument in usage.sortedArguments() %}
                        <tr><td {% if not argument.implemented %}
                                    class="unimplemented"
                                {% endif %}>
                                {{ argument.name }}</td>
                            <td>{{ argument.type }}</td>
                            <td>{% if argument.default == None %}
                                    &nbsp;
                                {% else %}
                                    {{ argument.default|string }}
                                {% endif %}</td>
                            <td>{{ argument.mandatory }}</td>
                            <td>{{ argument.description }}</td></tr>
                        {% endfor %}
                        </table>
                    {% endif %}
                    <!-- END USAGE ARGUMENTS -->

                    <!-- REQUEST PAYLOADS FOR THIS USAGE -->
                    {% if usage.requestPayloads %}
                        <h3>Request payload</h3>
                        {% set payloads = usage.requestPayloads.values() %}
                        <p>
                        {% if payloads|length > 1 %}
                            {% set showFormat = True %}
                            The request payload can be sent in any of
                            the following formats:
                        {% else %}
                            {% set showFormat = False %}
                            The request payload must be sent in
                            <span class="tt">{{ payloads[0].format }}</span>
                            format with the following fields:
                        {% endif %}
                        </p>

                        {% for payload in payloads %}
                            {% if showFormat %}
                                Payload format:
                                <span class="tt">{{ payload.format }}</span>,
                                with the following fields:<br/>
                            {% endif %}
                            <table>
                            <tr><th>Field name</th>
                                <th>Field type</th>
                                <th>Mandatory</th>
                                <th>Description</th></tr>
                            {% for field in payload.fields() %}
                                <tr>
                                <td><span class="tt">
                                    {{ field.name }}</span></td>
                                <td>{{ field.typeAsStr() }}</td>
                                <td>{{ field.mandatory }}</td>
                                <td>{{ field.description }}</td>
                                </tr>
                            {% endfor %}
                            </table>
                        {% endfor %}
                    {% endif %}
                    <!-- END REQUEST PAYLOADS -->

                    <!-- RESPONSE PAYLOADS FOR THIS USAGE -->
                    {% if usage.responsePayloads %}
                        <h3>Response payload</h3>
                        {% set payloads = usage.responsePayloads.values() %}
                        <p>
                        {% if payloads|length > 1 %}
                            {% set showFormat = True %}
                            You can request that the response payload
                            be sent in any of the following formats:
                        {% else %}
                            {% set showFormat = False %}
                            The response payload will be sent in
                            <span class="tt">{{ payloads[0].format }}</span>
                            format with the following fields:
                        {% endif %}
                        </p>

                        {% for payload in payloads %}
                            {% if showFormat %}
                                Payload format:
                                <span class="tt">{{ payload.format }}</span>,
                                with the following fields:<br/>
                            {% endif %}
                            <table>
                            <tr><th>Field name</th>
                                <th>Field type</th>
                                <th>Description</th></tr>
                            {% for field in payload.fields() %}
                                <tr>
                                <td><span class="tt">{{ field.name }}</span></td>
                                <td>{{ field.typeAsStr() }}</td>
                                <td>{{ field.description }}</td>
                                </tr>
                            {% endfor %}
                            </table>
                        {% endfor %}
                    {% endif %}
                    <!-- END RESPONSE PAYLOADS -->

                    <!-- EXAMPLES FOR THIS USAGE -->
                    {% if usage.examples %}
                        {% for example in usage.examples %}
                        <div class="http_example">
                            <h3>Example</h3>
                            {% if example.description %}
                            <p>{{example.description}}</p>
                            {% endif %}
                            <h4>Request</h4>
                            <div class="raw_http">
                                <pre>{{example.request}}</pre>
                            </div>
                            <h4>Response</h4>
                            <div class="raw_http">
                                <pre>{{example.response}}</pre>
                            </div>
                        </div>
                        {% endfor %}
                    {% endif %}
                    <!-- END EXAMPLES -->

                    <!-- RETURN CODES FOR THIS USAGE -->
                    {% if usage.returns %}
                        <h3>HTTP response status codes</h3>
                        <p>The following HTTP response codes may occur:</p>
                        <table>
                        <tr><th>Condition</th>
                            <th>Return</th></tr>
                        {% for return in usage.returns %}
                        <tr>
                            <td>{{ return.condition }}</td>
                            <td>{{ return.code }}</td>
                        </tr>
                        {% endfor %}
                        </table>
                    {% endif %}
                    <!-- END RETURN CODES -->

                    <!-- NOTES FOR THIS USAGE -->
                    {% if usage.notes %}
                        <div class="notes">
                        <h3>Note{% if usage.notes|length > 1 %}s{% endif %}:</h3>
                        <ol>
                        {% for note in usage.notes %}
                            <li>
                                <span class="note">
                                    {{ note.description }}
                                </span>
                            </li>
                        {% endfor %}
                        </ol>
                        </div>
                    {% endif %}
                    <!-- END USAGE NOTES -->
                </div>
            {% endfor %}
            <!-- END USAGE FOR LOOP FOR THIS FUNC -->
            </div>
        {% endif %}
        <!-- END IF USAGES FOR THIS FUNC -->
        </div>
    {% endfor %}
    <!-- END VERB/FUNC LOOP FOR THIS TOPLEVEL -->
    </div>
{% endfor %}
<!-- END FOR TOPLEVEL/VERB -->

</div> <!-- END OF API -->

<a name="typographic"></a>
<div class="typography">
  <hr/>
  <h2>Typographic conventions</h2>
  <p>The following typographic conventions are used above:</p>

  <ul>

    <li>URIs look like <span class="URI">/users/john</span>.</li>

    <li>When part of a URI is variable, it will look like
      <span class="URI">/users/<span class="var">USERNAME</span></span>
      (here <span class="var">USERNAME</span> is variable).</li>

    <li>The names of namespaces and tags in Fluidinfo look like
      <span class="tag">john/books/rating</span>.</li>

    <li>Variable parts of namespaces and tags are distinguished as
      with URIs, e.g.,
      <span class="tag">users/<span class="var">USERNAME</span></span>.
    </li>

    <li>Permissions look like <span class="perm">CREATE</span>,
      <span class="perm">READ</span>, <span class="perm">DELETE</span>,
      etc.</li>

    {% if showAdmin %}
    <li>Things that are typically only useful to administrators
      <span class="adminOnly">look like this</span></li>
    {% endif %}

    {% if showUnimplemented %}
    <li>Things that are not yet implemented
      <span class="unimplemented">look like this</span></li>
    {% endif %}

  </ul>
</div> <!-- typography -->

</div> <!-- document -->
</div> <!-- documentwrapper -->
</div> <!-- bodywrapper -->
</div> <!-- body -->

</body>
</html>
