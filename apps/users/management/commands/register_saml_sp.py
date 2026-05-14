from datetime import UTC, datetime
import json

from django.core.management.base import BaseCommand

# Minimal SP metadata XML. djangosaml2idp requires local_metadata with a validUntil
# attribute so it can determine when to refresh. Mixpanel does not publish SP metadata,
# so we construct the minimum required XML manually.
MIXPANEL_SP_METADATA_TEMPLATE = """<?xml version="1.0"?>
<md:EntityDescriptor
    xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{entity_id}"
    validUntil="{valid_until}">
  <md:SPSSODescriptor
      AuthnRequestsSigned="false"
      WantAssertionsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:AssertionConsumerService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="{acs_url}"
        index="1"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""


class Command(BaseCommand):
    help = "Register or update a SAML Service Provider entry"

    def add_arguments(self, parser):
        parser.add_argument("--entity-id", required=True)
        parser.add_argument("--acs-url", required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--processor", default="apps.users.saml_processor.MixpanelSAMLProcessor")
        parser.add_argument(
            "--attribute-mapping",
            default='{"email": "email", "name": "name"}',
        )

    def handle(self, *args, **options):
        from djangosaml2idp.models import ServiceProvider

        attribute_mapping = json.loads(options["attribute_mapping"])
        entity_id = options["entity_id"]
        acs_url = options["acs_url"]

        # 10-year expiry; renew by re-running this command
        valid_until = "2036-01-01T00:00:00Z"
        local_metadata = MIXPANEL_SP_METADATA_TEMPLATE.format(
            entity_id=entity_id,
            acs_url=acs_url,
            valid_until=valid_until,
        )

        try:
            sp = ServiceProvider.objects.get(entity_id=entity_id)
            created = False
        except ServiceProvider.DoesNotExist:
            sp = ServiceProvider(entity_id=entity_id)
            created = True

        sp.pretty_name = options["name"]
        sp.local_metadata = local_metadata
        sp.metadata_expiration_dt = datetime(2036, 1, 1, tzinfo=UTC)
        sp._attribute_mapping = attribute_mapping
        sp._processor = options["processor"]
        sp._sign_response = True
        sp._sign_assertion = True
        sp.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} ServiceProvider: {sp.entity_id}"))
        self.stdout.write(f"  ACS URL:            {acs_url}")
        self.stdout.write(f"  Processor:          {sp._processor}")
        self.stdout.write(f"  Attribute mapping:  {sp._attribute_mapping}")
