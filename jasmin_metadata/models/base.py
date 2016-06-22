"""
Django models for the JASMIN services app.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from picklefield.fields import PickledObjectField


class Metadatum(models.Model):
    """
    Model that allows the association of arbitrary data of any pickle-able
    type with any model instance.

    This is achieved by using the generic foreign key from the
    ``django.contrib.contenttypes`` module.
    """
    class Meta:
        verbose_name_plural = 'metadata'
        unique_together = ('content_type', 'object_id', 'key')

    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.CharField(max_length = 250)
    content_object = GenericForeignKey('content_type', 'object_id')
    #: The metadata key
    key = models.CharField(max_length = 200)
    #: The pickled value for the datum
    value = PickledObjectField(null = True)


class HasMetadata(models.Model):
    """
    Abstract base model for all models that need access to attached metadata.
    """
    class Meta:
        abstract = True

    metadata = GenericRelation(Metadatum, content_type_field = 'content_type',
                                          object_id_field = 'object_id')

    def copy_metadata_to(self, obj):
        """
        Finds all metadata entries associated with this object and copies them
        onto the given object.
        """
        content_type = ContentType.objects.get_for_model(obj)
        # Remove any existing metadata for the object
        Metadatum.objects.filter(content_type = content_type, object_id = obj.pk).delete()
        for datum in self.metadata.all():
            Metadatum.objects.create(
                content_type = content_type, object_id = obj.pk,
                key = datum.key, value = datum.value
            )
