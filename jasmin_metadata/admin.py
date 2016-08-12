"""
Module containing classes for integration of metadata with the Django admin site.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from functools import partial
from urllib.parse import urlencode

from django.contrib import admin
from django.contrib.admin.helpers import AdminForm
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django import forms
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.template.response import SimpleTemplateResponse
from django.contrib import messages
from django.utils.html import escape
from django.conf.urls import url
from django.contrib.admin import helpers
from django.utils.encoding import force_text

from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin, PolymorphicChildModelFilter
)

from .models import *


class FieldChoiceForm(forms.Form):
    """
    Use a select widget for the choice of field type instead of radio inputs.
    """
    ct_id = forms.ChoiceField(label = 'Field type', widget = forms.Select)


@admin.register(Field)
class FieldAdmin(PolymorphicParentModelAdmin):
    base_model = Field
    child_models = []
    add_type_form = FieldChoiceForm

    list_display = ('name', 'form')
    list_filter = ('form', )

    @classmethod
    def register_field_type(cls, model, model_admin = None):
        if not model_admin:
            model_admin = type(
                model._meta.model_name + 'Admin',
                (FieldChildAdmin, ),
                { 'base_model' : model }
            )
        cls.child_models.append((model, model_admin))


class FieldChildAdmin(PolymorphicChildModelAdmin):
    # The field on objects in this admin that we want to redirect to
    redirect_to_field = 'form'

    def response_post_save_add(self, request, obj):
        redirect_to = getattr(obj, self.redirect_to_field, None)
        if not redirect_to:
            return super().response_post_save_add(request, obj)
        else:
            return redirect(
                'admin:{}_{}_change'.format(
                    redirect_to._meta.app_label, redirect_to._meta.model_name
                ),
                redirect_to.pk
            )

    def response_post_save_change(self, request, obj):
        redirect_to = getattr(obj, self.redirect_to_field, None)
        if not redirect_to:
            return super().response_post_save_change(request, obj)
        else:
            return redirect(
                'admin:{}_{}_change'.format(
                    redirect_to._meta.app_label, redirect_to._meta.model_name
                ),
                redirect_to.pk
            )

    def delete_model(self, request, obj):
        # HACK
        # Before we delete the object, store the object we want to redirect to on
        # the request for later
        redirect_to = getattr(obj, self.redirect_to_field, None)
        request._redirect_to_obj_ = redirect_to
        return super().delete_model(request, obj)

    def response_delete(self, request, obj_display, obj_id):
        ## COPIED FROM django/contrib/admin/options.py
        if "_popup" in request.POST:
            return SimpleTemplateResponse('admin/popup_response.html', {
                'action': 'delete',
                'value': escape(obj_id),
            })

        self.message_user(request,
            _('The %(name)s "%(obj)s" was deleted successfully.') % {
                'name': force_text(opts.verbose_name),
                'obj': force_text(obj_display),
            }, messages.SUCCESS)
        # END COPIED SECTION

        redirect_to = getattr(request, '_redirect_to_obj_', None)
        if not redirect_to:
            return super().response_delete(request, obj_display, obj_id)
        else:
            return redirect(
                'admin:{}_{}_change'.format(
                    redirect_to._meta.app_label, redirect_to._meta.model_name
                ),
                redirect_to.pk
            )

class UserChoiceInline(admin.TabularInline):
    model = UserChoice
    prepopulated_fields = { 'display' : ('value', ) }

class ChoiceFieldAdmin(FieldChildAdmin):
    base_model = ChoiceField
    inlines = (UserChoiceInline, )

class MultipleChoiceFieldAdmin(FieldChildAdmin):
    base_model = MultipleChoiceField
    inlines = (UserChoiceInline, )


FieldAdmin.register_field_type(BooleanField)
FieldAdmin.register_field_type(SingleLineTextField)
FieldAdmin.register_field_type(MultiLineTextField)
FieldAdmin.register_field_type(EmailField)
FieldAdmin.register_field_type(IPv4Field)
FieldAdmin.register_field_type(RegexField)
FieldAdmin.register_field_type(SlugField)
FieldAdmin.register_field_type(URLField)
FieldAdmin.register_field_type(IntegerField)
FieldAdmin.register_field_type(FloatField)
FieldAdmin.register_field_type(ChoiceField, ChoiceFieldAdmin)
FieldAdmin.register_field_type(MultipleChoiceField, MultipleChoiceFieldAdmin)
FieldAdmin.register_field_type(DateField)
FieldAdmin.register_field_type(DateTimeField)
FieldAdmin.register_field_type(TimeField)


class FieldInline(admin.TabularInline):
    template = 'admin/polymorphic_inline_tabular.html'
    extra = 0
    model = Field
    fields = ('name', 'field_info', 'required', 'position', )
    readonly_fields = ('name', 'field_info', 'required')
    formfield_overrides = {
        models.TextField : {
            'widget' : forms.Textarea(attrs = { 'rows' : 3 }),
        },
    }

@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    inlines = (FieldInline, )
    list_display = ('name', 'n_fields')

    def n_fields(self, obj):
        return obj.fields.count()
    n_fields.short_description = '# fields'


################################################################################
################################################################################


class HasMetadataModelAdmin(admin.ModelAdmin):
    """
    ``ModelAdmin`` for use with models that may have metadata attached.
    """
    #: The metadata form class to use
    #: Must inherit from :py:class:`~.models.MetadataForm`
    metadata_form_class = None

    change_form_template = 'admin/change_form_metadata.html'

    def get_metadata_form_class(self, request, obj):
        """
        Returns the metadata form to use for the given object.

        The returned form must inherit from :py:class:`~.forms.MetadataForm`.
        """
        return self.metadata_form_class

    def get_metadata_form_initial_data(self, request, obj):
        """
        Gets the initial data for the metadata form. By default, this just
        returns the metadata currently attached to the object.
        """
        ctype = ContentType.objects.get_for_model(obj)
        metadata = Metadatum.objects.filter(content_type = ctype, object_id = obj.pk)
        return { d.key : d.value for d in metadata.all() }

    def save_model(self, request, obj, form, change):
        #####
        ## Override save_model to only save the model if the metadata is also valid
        #####
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().save_model(request, obj, form, change)
        # If the metadata is valid, save the object and the metadata
        if '_has_metadata' in request.POST:
            metadata_form = metadata_form_class(data = request.POST, prefix = 'metadata')
            if metadata_form.is_valid():
                super().save_model(request, obj, form, change)
                metadata_form.save(obj)

    def response_add(self, request, obj, post_url_continue = None):
        #####
        ## Override response_add to collect metadata after the object is fully
        ## specified
        ##
        ## This is primarily to allow us to deal with the situation where the
        ## required metadata is dependent on an objects state in an intuitive way
        #####
        # If there is no metadata form, behave as normal
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().response_add(request, obj, post_url_continue)
        if '_has_metadata' in request.POST:
            # If the submit supposedly has metadata, validate it
            # If the metadata is valid (and hence has been saved), behave as normal
            metadata_form = metadata_form_class(data = request.POST, prefix = 'metadata')
            if metadata_form.is_valid():
                return super().response_add(request, obj, post_url_continue)
        else:
            # If there is no metadata in the submit, create the form
            metadata_form = metadata_form_class(
                initial = self.get_metadata_form_initial_data(request, obj),
                prefix = 'metadata'
            )
        #######
        ## THIS CODE IS SIMILAR TO changeform_view
        #######
        # When rendering the metadata form, we also render the object form with
        # all the elements hidden
        parent_form_class = self.get_form(request)
        parent_form = parent_form_class(request.POST, request.FILES)
        # Make all the fields in the parent form hidden
        for field in parent_form.fields:
            parent_form.fields[field].widget = forms.HiddenInput()
        admin_form = helpers.AdminForm(
            parent_form,
            list(self.get_fieldsets(request, obj)),
            self.get_prepopulated_fields(request, obj),
            self.get_readonly_fields(request, obj),
            model_admin = self
        )
        media = self.media + admin_form.media
        metadata_admin_form = helpers.AdminForm(
            metadata_form,
            # Put all the fields in one fieldset
            [(None, { 'fields' : list(metadata_form.fields.keys()) })],
            # No pre-populated fields
            {},
        )
        errors = helpers.AdminErrorList(parent_form, [])
        if metadata_form.errors:
            errors.extend(metadata_form.errors.values())
        context = dict(self.admin_site.each_context(request),
            title = 'Set metadata for {}'.format(force_text(self.model._meta.verbose_name)),
            adminform = admin_form,
            metadata_form = metadata_admin_form,
            object_id = obj.pk,
            original = obj,
            is_popup = ("_popup" in request.POST or "_popup" in request.GET),
            to_field = request.POST.get("_to_field", request.GET.get("_to_field")),
            media = media,
            inline_admin_formsets = [],
            errors = errors,
            preserved_filters = self.get_preserved_filters(request),
        )
        return self.render_change_form(request, context, add = True, change = False, obj = obj)

    def response_change(self, request, obj):
        #####
        ## Override response_change to ensure that the metadata is valid before
        ## proceeding with the normal action
        #####
        # If there is no metadata form, behave as normal
        metadata_form_class = self.get_metadata_form_class(request, obj)
        # If there is no metadata form, behave as normal
        if not metadata_form_class:
            return super().response_change(request, obj)
        if '_has_metadata' in request.POST:
            # If the submit supposedly has metadata, validate it
            # If the metadata is valid (and hence has been saved), behave as normal
            metadata_form = metadata_form_class(data = request.POST, prefix = 'metadata')
            if metadata_form.is_valid():
                return super().response_change(request, obj)
        #######
        ## If metadata is invalid, we essentially need to replicate part of
        ## changeform_view to re-display the form
        #######
        parent_form_class = self.get_form(request)
        parent_form = parent_form_class(request.POST, request.FILES, instance = obj)
        admin_form = helpers.AdminForm(
            parent_form,
            list(self.get_fieldsets(request, obj)),
            self.get_prepopulated_fields(request, obj),
            self.get_readonly_fields(request, obj),
            model_admin = self
        )
        media = self.media + admin_form.media
        context = dict(self.admin_site.each_context(request),
            title = 'Change {}'.format(force_text(self.model._meta.verbose_name)),
            adminform = admin_form,
            object_id = obj.pk,
            original = obj,
            is_popup = ("_popup" in request.POST or "_popup" in request.GET),
            to_field = request.POST.get("_to_field", request.GET.get("_to_field")),
            media = media,
            inline_admin_formsets = [],
            errors = helpers.AdminErrorList(parent_form, []),
            preserved_filters = self.get_preserved_filters(request),
        )
        return self.render_change_form(request, context, add = False, change = True, obj = obj)

    def render_change_form(self, request, context, add = False,
                                 change = False, form_url = '', obj = None):
        #####
        ## Override render_change_form to show the metadata form as an additional
        ## fieldset on change pages
        #####
        if change:
            metadata_form_class = self.get_metadata_form_class(request, obj)
            if metadata_form_class:
                if request.method == 'POST':
                    metadata_form = metadata_form_class(data = request.POST, prefix = 'metadata')
                    # Force a validation - we don't really care about the result here
                    metadata_form.is_valid()
                else:
                    # If there is no metadata in the submit, create the form
                    metadata_form = metadata_form_class(
                        initial = self.get_metadata_form_initial_data(request, obj),
                        prefix = 'metadata'
                    )
            context['metadata_form'] = helpers.AdminForm(
                metadata_form,
                # Put all the fields in one fieldset
                [('Metadata', { 'fields' : list(metadata_form.fields.keys()) })],
                # No pre-populated fields
                {},
            )
            context['errors'].extend(metadata_form.errors.values())
        return super().render_change_form(request, context, add, change, form_url, obj)