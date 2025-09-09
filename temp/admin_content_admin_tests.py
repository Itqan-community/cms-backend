from django.test import Client
from django.conf import settings
from django.urls import reverse
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from apps.content.models import (
    PublishingOrganization, PublishingOrganizationMember, License, Resource,
    ResourceVersion, Asset, AssetVersion, AssetAccessRequest, AssetAccess,
    UsageEvent, Distribution
)
from apps.accounts.models import Role

User = get_user_model()

# Ensure roles
for role_name in ['Admin','Publisher','Developer','Reviewer']:
    Role.objects.get_or_create(name=role_name, defaults={'description': role_name})

# Ensure admin user
admin = User.objects.filter(email='admin@localhost').first()
if not admin:
    admin = User.objects.create_superuser(username='admin', email='admin@localhost', password='ItqanCMS2024!')
    admin.role = Role.objects.get(name='Admin')
    admin.save()

# Ensure developer user
dev = User.objects.filter(email='dev@localhost').first()
if not dev:
    dev = User.objects.create_user(username='dev', email='dev@localhost', password='devpass')
    dev.role = Role.objects.get(name='Developer')
    dev.save()

# Seed data
org, _ = PublishingOrganization.objects.get_or_create(name='Admin Org', slug='admin-org')
PublishingOrganizationMember.objects.get_or_create(publishing_organization=org, user=admin, defaults={'role':'owner'})
lic, _ = License.objects.get_or_create(code='cc0', defaults={'name':'CC0 - Public Domain', 'is_default': True})
res, _ = Resource.objects.get_or_create(
    publishing_organization=org, name='Sample Resource', slug='sample-resource',
    defaults={'description':'Test resource', 'category':'mushaf', 'status':'draft', 'default_license': lic}
)
if not res.default_license_id:
    res.default_license = lic
    res.category = 'mushaf'
    res.status = 'draft'
    res.save()

rv = ResourceVersion.objects.filter(resource=res, semvar='1.0.0').first()
if not rv:
    rv = ResourceVersion.objects.create(resource=res, name=res.name, summary='v1', semvar='1.0.0', type='csv', size_bytes=12, is_latest=True)
    rv.storage_url.save('res.json', ContentFile(b'{"ok":true}'), save=True)

asset, _ = Asset.objects.get_or_create(
    resource=res, name='asset-a',
    defaults={'title':'Asset A', 'description':'Test asset', 'long_description':'', 'category':'mushaf', 'license': lic,
              'file_size':'1 MB', 'format':'CSV', 'version':'1.0', 'language':'en', 'encoding':'UTF-8'}
)

av = asset.get_latest_version()
if not av:
    av = AssetVersion.objects.create(asset=asset, resource_version=rv, name='Asset A v1', summary='initial', size_bytes=22)
    av.file_url.save('asset.csv', ContentFile(b'id,title\n1,Test'), save=True)

# Ensure access
aar = AssetAccessRequest.objects.filter(developer_user=dev, asset=asset).first()
if not aar:
    aar = AssetAccessRequest.objects.create(developer_user=dev, asset=asset, developer_access_reason='Testing', intended_use='non-commercial')
    aar.approve_request(approved_by_user=admin, auto_approved=False)

UsageEvent.objects.get_or_create(developer_user=dev, usage_kind='file_download', subject_kind='asset', asset_id=asset.id, defaults={'metadata': {'note':'test'}})
Distribution.objects.get_or_create(resource=res, format_type='ZIP', endpoint_url='https://example.com/sample.zip', version='1.0.0')

# Allow test client host
try:
    if 'testserver' not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append('testserver')
except Exception:
    pass

# Admin client
client = Client()
client.force_login(admin)

model_ids = []
model_ids.append(('publishingorganization', org.id))
member = PublishingOrganizationMember.objects.filter(publishing_organization=org, user=admin).first()
model_ids.append(('publishingorganizationmember', member.id))
model_ids.append(('license', lic.id))
model_ids.append(('resource', res.id))
model_ids.append(('resourceversion', rv.id))
model_ids.append(('asset', asset.id))
model_ids.append(('assetversion', av.id))
access = AssetAccess.get_user_access(dev, asset)
if access:
    model_ids.append(('assetaccess', access.id))
model_ids.append(('assetaccessrequest', aar.id))
ue = UsageEvent.objects.filter(developer_user=dev).first()
if ue:
    model_ids.append(('usageevent', ue.id))
dist = Distribution.objects.filter(resource=res).first()
if dist:
    model_ids.append(('distribution', dist.id))

# Exercise admin views
results = []
for model_name, obj_id in model_ids:
    changelist = reverse(f'admin:content_{model_name}_changelist')
    add = reverse(f'admin:content_{model_name}_add')
    change = reverse(f'admin:content_{model_name}_change', args=[obj_id])
    r1 = client.get(changelist)
    r2 = client.get(add)
    r3 = client.get(change)
    results.append((model_name, r1.status_code, r2.status_code, r3.status_code))

for row in results:
    print(f"{row[0]} -> list:{row[1]} add:{row[2]} change:{row[3]}")
