<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="{{ LANGUAGE_CODE }}" xml:lang="{{ LANGUAGE_CODE }}" {% if LANGUAGE_BIDI %}dir="rtl"{% endif %}>
<head>
<title>{% block title %}Fluidinfo permissions{% endblock %}</title>
<link rel="stylesheet" type="text/css" href="{% block stylesheet %}../css/api.css{% endblock %}" />
{% block extrastyle %}{% endblock %}
{% block extrahead %}{% endblock %}
{% block blockbots %}<meta name="robots" content="NONE,NOARCHIVE" />{% endblock %}
</head>

{% macro attrWrap(what) -%}
<span class="attr">{{what}}</span>
{%- endmacro %}

{% macro permWrap(what) -%}
<span class="perm">{{what}}</span>
{%- endmacro %}

{% macro attr(what) -%}
{{ attrWrap(what) }}
{%- endmacro %}

{% macro obj(what) -%}
<span class="obj">OBJ({{ attr(what) }})</span>
{%- endmacro %}

{# Regular permissions. #}

{% macro policyAttr(category, action) -%}
{{ attrWrap(info['permTagPolicyPath'](category, action)) }}
{%- endmacro %}

{% macro exceptionsAttr(category, action) -%}
{{ attrWrap(info['permTagExceptionsPath'](category, action)) }}
{%- endmacro %}

{% macro permAttrNS(category) -%}
{{ attrWrap(info['permTagNamespacePath'](category)) }}
{%- endmacro %}

{# New user default permissions. #}

{% macro defaultPermAttrNS(category) -%}
{{ attrWrap(info['defaultPermTagNamespacePath'](category)) }}
{%- endmacro %}

{% macro defaultPolicyAttr(category, action) -%}
{{ attrWrap(info['defaultPermTagPolicyPath'](category, action)) }}
{%- endmacro %}

{% macro defaultExceptionsAttr(category, action) -%}
{{ attrWrap(info['defaultPermTagExceptionsPath'](category, action)) }}
{%- endmacro %}

{% set namespace = info['namespaceCategoryName'] %}
{% set tag = info['tagCategoryName'] %}
{% set tagInstanceSet = info['tagInstanceSetCategoryName'] %}

{% set namespaceNS = permAttrNS(namespace) %}
{% set tagNS = permAttrNS(tag) %}
{% set tagInstanceSetNS = permAttrNS(tagInstanceSet) %}

{% set open = '"' + info['open'] + '"' %}
{% set closed = '"' + info['closed'] + '"' %}

{% set control = info['control'] %}
{% set create = info['create'] %}
{% set delete = info['delete'] %}
{% set list = info['list'] %}
{% set read = info['read'] %}
{% set update = info['update'] %}

{% set controlPerm = permWrap(info['control']) %}
{% set createPerm = permWrap(info['create']) %}
{% set deletePerm = permWrap(info['delete']) %}
{% set listPerm = permWrap(info['list']) %}
{% set readPerm = permWrap(info['read']) %}
{% set updatePerm = permWrap(info['update']) %}

{% set USERNAME = '<span class="var">USERNAME</span>' %}

<body>
    <div class="document">
      <div class="documentwrapper">
        <div class="bodywrapper">
          <div class="body">
<div class="intro">
<h1>The Fluidinfo permissions system</h1>

<p>
Here is a description of the permissions system used in Fluidinfo.
Some terminology and things to bear in mind:
</p>

<ul>
<li>
<p>
There are two things in Fluidinfo that are subject to permissions control:
<em>namespaces</em> and <em>tags</em>. These are treated in a uniform
manner.
</p>
</li>

<li>
<p>
Users attempt to carry out <em>actions</em> on namespaces and tags.
</p>
</li>

<li>It is important to understand the difference between a tag itself and
the (possibly zero, possibly many) occurrences of that tag on Fluidinfo
objects. To illustrate, we might have a tag {{ attr('fred/rating') }} that
Fred intends to use to rate things. The Fred user initially creates the tag
itself, but at that point has not used it to tag anything.  The tag
exists, but its set of occurrences on objects is still empty.
</p>

<p>
When Fred decides to rate something, say with a 6, a tag with that value is
created and attached to a Fluidinfo object. If he later rates another object
as a 3, another {{ attr('fred/rating') }} tag is created and attached to
the other object.
</p>

<p>
For the purposes of permissions checking, Fluidinfo considers what we'll call
the <em>tag itself</em> to be different from the set of its occurrences on
objects. Using Fluidinfo permissions you could, for example, grant permission
to others to alter occurrences of {{ attr('fred/rating') }} (e.g., change a 3
rating to a 4), but not permission to alter the tag itself (e.g., its
description).
</p></li>

{#
<li>
<p>
Applications are users too. This means that when someone is using an
application, there are potentially two Fluidinfo users interacting with
Fluidinfo: the (human) user sitting in front of a computer or mobile device
etc., and the application itself, which may be managing its own data inside
Fluidinfo. Thus the application will make some API calls on behalf of the
human user.
</p>
</li>
#}

<li>
<p>
Permissions are checked every time an application, on behalf of either a
user or itself, uses the Fluidinfo API to attempt to perform an action on a
namespace or tag.
</p>
</li>

<li>
<p>
To denote the object that corresponds to a namespace or tag, e.g., {{
attr('fred/rating') }}, we will use {{ obj('fred/rating') }}.
</p>
</li>

<li>
<p>
In case you are asking yourself about permissions on objects: <em>Objects in
Fluidinfo have no permissions.</em>
</p>
</li>

</ul>

<h1>Actions</h1>

Here are the actions that can be taken on namespaces, tags themselves, and
sets of tag occurrences.

<h2>Namespaces</h2>

<p>
The available actions on namespaces are:
</p>

<ul>
 <li>{{ createPerm }} - create namespaces or tags in a given namespace.</li>
 <li>{{ updatePerm }} - change the properties (e.g., description) of a
                        namespace.</li>
 <li>{{ deletePerm }} - delete the namespace, which must be empty.</li>
 <li>{{ listPerm }} - see the names of contained namespaces and tags.</li>
</ul>

<h2>Tags themselves</h2>

<p>
The available actions on a tag itself are:
</p>

<ul>
 <li>{{ updatePerm }} - change the tag itself, e.g., its description.</li>
 <li>{{ deletePerm }} - delete the tag (and all its occurrences).</li>
</ul>

<h2>Sets of tag occurrences</h2>

<p>
The available actions on the set of occurrences of a tag are:
</p>

<ul>
 <li>{{ createPerm }} - add a tag to an object.</li>
 <li>{{ readPerm }} - read the value of a tag on an object.</li>
 <li>{{ deletePerm }} - remove a tag from an object.</li>
</ul>


<h1>Checking permissions</h1>

<p>
The permission for each action are implemented as a policy (set to either {{
open }} or {{ closed }}), and zero or more exceptions to the policy. An API
call is allowed to proceed if the permission for the action is either
</p>

<ol>
 <li>an {{ open }} policy and the user not in the exceptions, or</li>
 <li>a {{ closed }} policy and the user in the exceptions.</li>
</ol>

<p>
Permission information for namespaces and tags is stored in instances of
other Fluidinfo tags. That is, <em>Fluidinfo uses (other) tags to store
permissions about namespaces and tags.</em> This is a conceptually simple
approach, but it needs some care when thinking about changing permissions -
who has permission to change a permission? We'll answer that below.
</p>

<p>
Permission tags live under the following Fluidinfo namespaces:

<ul>
<li>{{ namespaceNS }}</li>
<li>{{ tagNS }}</li>
<li>{{ tagInstanceSetNS }}</li>
</ul>
</p>

<p>
For each action for each of these categories, there are two corresponding
tags: one for the policy and one for its exception list. For example,
permission information about who can create a tag in a namespace is stored
in instances of the two tags

<ul>
<li>{{ policyAttr(namespace, create) }}</li>
<li>{{ exceptionsAttr(namespace, create) }}</li>
</ul>
</p>

<p>
So those are the <em>tags</em> involved in permissions checking. But
what about the occurrences of those tags, encoding access to a specific
namespace or tag?
</p>

<p>
Instances of the permission tags are stored <em>on objects that corresponds
to the namespaces and tags.</em> E.g., the permissions information for a
tag {{ attr('fred/rating') }} is stored in permission tag instances on {{
obj('fred/rating') }}.
</p>

<p>
To be more concrete, suppose a user is trying to delete the tag {{
attr('fred/rating') }}.  Fluidinfo will examine the tags {{
policyAttr(tag, delete) }} and {{ exceptionsAttr(tag, delete)
}} on {{ obj('fred/rating') }} for the open/closed policy and its
exceptions.
</p>

<p>
As a second example, suppose there is a namespace {{ attr('fred/books') }}.
The object associated with it, {{ obj('fred/books') }}, will have tags {{
policyAttr(namespace, create) }} and {{ exceptionsAttr(namespace, create)
}} on it. The values of those tags indicate which Fluidinfo users are allowed
to create namespaces or tags in {{ attr('fred/books') }}.  Similarly, {{
obj('fred/books') }} will also have instances of {{ policyAttr(namespace,
update) }}, {{ exceptionsAttr(namespace, update) }}, etc., for each of the
other actions relevant to namespaces.
</p>

<p>
Note that the permissions for a tag itself and the permissions for its
occurrences are both stored on the same object. There is no possibility of
collision because the tags holding permissions for the tag itself are under
the {{ tagNS }} namespace while those for its occurrences
are under the {{ tagInstanceSetNS }} namespace.
</p>


<h1>Changing permissions</h1>

<p>
When taking an action on a tag, we have to consider whether it is a
permission tag.  In the simple case, when it is not a permission tag,
Fluidinfo decides whether to allow the action using the normal
policy/exception permissions tags as described above.
</p>

<p>
Otherwise, the user is trying to change a permission tag. Here we do not
use the regular permission system to hold information about permissions
because that would be circular.
</p>

<p>
Instead, to check whether a user is allowed to alter a permission tag, two
other policy/exception atttributes are consulted. These are the permission
{{ controlPerm }} tags, located alongside the regular permissions tags in
the namespaces

<ul>
<li>{{ namespaceNS }}</li>
<li>{{ tagNS }}</li>
<li>{{ tagInstanceSetNS }}</li>
</ul>

For example, the tags controlling permission over tags are {{
policyAttr(tag, control) }} and {{ exceptionsAttr(tag, control)
}}.  As with regular permissions tags, instances of the control tags are
also stored on objects corresponding to specific namespaces and tags.
</p>

<p>
That means that there are really two kinds of permission tags: regular and
control. We need to consider how instances of these two types can be
changed.
</p>

<h2>Changing a regular permission tag</h2>

<p>
When a user attempts an operation on a regular (non-control) permission
tag under any of

<ul>
  <li>{{ namespaceNS }}</li>
  <li>{{ tagNS }} or</li>
  <li>{{ tagInstanceSetNS }}</li>
</ul>

they are necessarily attempting to change the permission for <em>another
namespace or tag.</em> We know that because these permission tags only
appear on objects that correspond to namespaces and tags. (Actually, this
is not 100% correct: each of the permission tags is also on the user's
object - to hold the user's default permissions settings for the new
namespaces or tags they create.)
</p>

<p>
In these cases we consult the policy and exception list given by the
instance of the control tag on the same object.
</p>


<h3>Inverting the policy on a regular permission tag</h3>

<p>
When changing a policy from {{ open }} to {{ closed }} on a non-control
permission tag, the instance of the exceptions tag is set to the empty
set. It is probably an error to leave a non-empty exceptions list intact:
the point of changing a policy from {{ open }} to {{ closed }} is to keep
users out by default, and that policy should definitely apply to the users
who were already excluded. Leaving the exceptions list intact would be
granting permission to those who were formerly explicitly excluded due to
the previous {{ open }} policy.
</p>

<p>
Similarly, when changing a policy from {{ closed }} to {{ open }}, the
instance of the exceptions tag is set to the empty set. Users who were on
the old exceptions list (i.e., who had access) should continue to have
access. Not clearing the exceptions list would deny them access under the
new {{ open }} policy.
</p>

<h2>Changing a control permission tag</h2>

<p>
When a user tries to change a permission control tag, we simply check the
policy and exceptions list of the control tag.
</p>

<p>
That means that a user who has control over a namespace or tag can
remove/grant control over that thing for others. It also means that a user
with control can remove themselves from the group of users with control.
</p>

<h3>Inverting the policy on a control permission tag</h3>

<p>
The comments about clearing the exceptions list when a policy is changed on
a regular permission tag also apply to a control permission
tag, but with one variation.
</p>

<p>
If a control policy is changed to {{ closed }}, the user making the change
is added to the exceptions list. This is legitimate, seeing as that user
must have originally had control to even be making this change. We are
simply preserving that user's control. If we did not put the user into the
exceptions list, no-one would be able to control the permissions on the
namespace, tag, or tag instance set.
</p>

<p>
It is still possible for someone with control to take away control for
everyone, including themselves. They just have to set the policy to {{
closed }} (if it is not already) and <em>then</em> remove themselves from
the exceptions list.  Note that this might be a desirable state of affairs.
For example, one could put a tag on a number of objects and then set
permissions so no further occurrences of the tag could be created by
anyone. You would do this by first setting the policy of the create action
for the tag to be closed, with no exceptions. Then, set the policy for the
control permission of the tag to be closed. Then remove yourself from the
exceptions list of the control tag. At that point no-one has permission to
add the tag to objects, and no-one has the right to change that permission
list. If the permissions tags are readable, others can verify this fact.
</p>



<h1>Setting permissions on new namespaces and tags</h1>

<p>
When a user creates a new namespace or tag, the policy and exceptions for
each of the relevant permission actions are copied from tags on the user's
own object onto the object created for the new namespace or tag.
</p>

<p>
I.e., we copy the values of {{ policyAttr(namespace, create) }} and {{
exceptionsAttr(namespace, create) }} etc., for all permission tags from the
user's object into new occurences of the same tags on the newly-created
object created for the new namespace or tag.
</p>

<h1>Setting permission defaults for new users</h1>

<p>
When a new user is created in Fluidinfo, a set of permission defaults is set
for them.  These are the permissions that will be used on the namespaces
and tags that the user creates in the future, as just described.
</p>

<p>
The values for system-wide default permissions for new users, are found in

{{ defaultPolicyAttr(namespace, create) }} and
{{ defaultExceptionsAttr(namespace, create) }} etc.

tags on the system administrator's object and are copied into
the corresponding tags

{{ policyAttr(namespace, create) }} and
{{ exceptionsAttr(namespace, create) }} etc.

that are placed onto the freshly-created object for the new user.
</p>



<h1>All permission tags</h1>

<p>
Here is a list of all permissions tags. As described above, these tags
appear on the objects for all users, namespaces, and tags.

<ul>
  {% for attr in info['allPermTags'] %}
    <li>{{ attrWrap(attr) }}</li>
  {% endfor %}
</ul>

And here are all the system default permission tags. A single occurrence of
each of these is stored on the system administrator's object.

<ul>
  {% for attr in info['allDefaultPermTags'] %}
    <li>{{ attrWrap(attr) }}</li>
  {% endfor %}
</ul>

</p>

</div> <!-- intro -->
</div>
</div>
</div>
</div>
</body>
</html>
