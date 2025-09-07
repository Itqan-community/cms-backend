"""
Management command to seed default licenses into the database.
Implements the v1 license specifications from task requirements.
"""

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from apps.content.models import License


class Command(BaseCommand):
    help = "Seed default licenses as specified in v1 requirements"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update existing licenses",
        )

    def handle(self, *args, **options):
        force_update = options["force"]

        # Default licenses as specified in task requirements
        default_licenses = [
            {
                "code": "cc0",
                "name": "CC0 - Public Domain",
                "short_name": "CC0",
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/png/cc-zero.png",
                "summary": "No rights reserved. You can copy, modify, distribute and perform the work, even for commercial purposes, all without asking permission.",
                "full_text": "The Creative Commons CC0 Public Domain Dedication waives copyright interest in a work you have created and dedicates it to the world-wide public domain.",
                "legal_code_url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
                "is_default": True,
                "license_terms": [
                    {
                        "title": "Public Domain Dedication",
                        "title_ar": "إهداء للملك العام",
                        "description": "This work has been identified as being free of known restrictions under copyright law.",
                        "description_ar": "تم تحديد هذا العمل على أنه خالٍ من القيود المعروفة بموجب قانون حقوق الطبع والنشر.",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "label_ar": "الاستخدام التجاري",
                        "description": "You may use the material for commercial purposes.",
                        "description_ar": "يمكنك استخدام المواد لأغراض تجارية.",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "label_ar": "التعديل",
                        "description": "You may adapt, remix, transform, and build upon the material.",
                        "description_ar": "يمكنك تكييف وإعادة مزج وتحويل والبناء على المواد.",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "label_ar": "التوزيع",
                        "description": "You may copy and redistribute the material in any medium or format.",
                        "description_ar": "يمكنك نسخ وإعادة توزيع المواد في أي وسيط أو تنسيق.",
                    },
                ],
                "conditions": [],
                "limitations": [],
            },
            {
                "code": "cc-by-4.0",
                "name": "Creative Commons Attribution 4.0",
                "short_name": "CC BY 4.0",
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by.png",
                "summary": "You are free to use, share and adapt this work as long as you give appropriate credit.",
                "full_text": "You are free to: Share — copy and redistribute the material in any medium or format. Adapt — remix, transform, and build upon the material for any purpose, even commercially.",
                "legal_code_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                "is_default": False,
                "license_terms": [
                    {
                        "title": "Attribution Required",
                        "title_ar": "الإسناد مطلوب",
                        "description": "You must give appropriate credit, provide a link to the license, and indicate if changes were made.",
                        "description_ar": "يجب أن تعطي الائتمان المناسب، وتوفر رابط إلى الترخيص، وتشير إلى ما إذا كانت قد تم إجراء تغييرات.",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "label_ar": "الاستخدام التجاري",
                        "description": "You may use the material for commercial purposes.",
                        "description_ar": "يمكنك استخدام المواد لأغراض تجارية.",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "label_ar": "التعديل",
                        "description": "You may adapt, remix, transform, and build upon the material.",
                        "description_ar": "يمكنك تكييف وإعادة مزج وتحويل والبناء على المواد.",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "label_ar": "التوزيع",
                        "description": "You may copy and redistribute the material in any medium or format.",
                        "description_ar": "يمكنك نسخ وإعادة توزيع المواد في أي وسيط أو تنسيق.",
                    },
                ],
                "conditions": [
                    {
                        "key": "attribution",
                        "label": "Attribution",
                        "label_ar": "الإسناد",
                        "description": "You must give appropriate credit.",
                        "description_ar": "يجب أن تعطي الائتمان المناسب.",
                    },
                ],
                "limitations": [
                    {
                        "key": "warranty",
                        "label": "No warranties",
                        "label_ar": "لا ضمانات",
                        "description": "The license may not give you all of the permissions necessary for your intended use.",
                        "description_ar": "قد لا يمنحك الترخيص جميع الأذونات اللازمة للاستخدام المقصود.",
                    },
                ],
            },
            {
                "code": "cc-by-sa-4.0",
                "name": "Creative Commons Attribution-ShareAlike 4.0",
                "short_name": "CC BY-SA 4.0",
                "url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-sa.png",
                "summary": "You are free to use, share and adapt this work as long as you give appropriate credit and share under the same license.",
                "full_text": "You are free to share and adapt the material for any purpose, even commercially, under the following terms: Attribution and ShareAlike.",
                "legal_code_url": "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
                "is_default": False,
                "license_terms": [
                    {
                        "title": "Attribution and ShareAlike Required",
                        "title_ar": "الإسناد والمشاركة بنفس الطريقة مطلوبة",
                        "description": "You must give appropriate credit and share under the same license.",
                        "description_ar": "يجب أن تعطي الائتمان المناسب وتشارك تحت نفس الترخيص.",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "label_ar": "الاستخدام التجاري",
                        "description": "You may use the material for commercial purposes.",
                        "description_ar": "يمكنك استخدام المواد لأغراض تجارية.",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "label_ar": "التعديل",
                        "description": "You may adapt, remix, transform, and build upon the material.",
                        "description_ar": "يمكنك تكييف وإعادة مزج وتحويل والبناء على المواد.",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "label_ar": "التوزيع",
                        "description": "You may copy and redistribute the material in any medium or format.",
                        "description_ar": "يمكنك نسخ وإعادة توزيع المواد في أي وسيط أو تنسيق.",
                    },
                ],
                "conditions": [
                    {
                        "key": "attribution",
                        "label": "Attribution",
                        "label_ar": "الإسناد",
                        "description": "You must give appropriate credit.",
                        "description_ar": "يجب أن تعطي الائتمان المناسب.",
                    },
                    {
                        "key": "share_alike",
                        "label": "ShareAlike",
                        "label_ar": "المشاركة بنفس الطريقة",
                        "description": "If you remix, transform, or build upon the material, you must distribute your contributions under the same license.",
                        "description_ar": "إذا كنت تعيد المزج أو التحويل أو البناء على المواد، يجب عليك توزيع مساهماتك تحت نفس الترخيص.",
                    },
                ],
                "limitations": [
                    {
                        "key": "warranty",
                        "label": "No warranties",
                        "label_ar": "لا ضمانات",
                        "description": "The license may not give you all of the permissions necessary for your intended use.",
                        "description_ar": "قد لا يمنحك الترخيص جميع الأذونات اللازمة للاستخدام المقصود.",
                    },
                ],
            },
            {
                "code": "mit",
                "name": "MIT License",
                "short_name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
                "icon_url": "https://upload.wikimedia.org/wikipedia/commons/0/0c/MIT_logo.svg",
                "summary": "A short and simple permissive license with conditions only requiring preservation of copyright and license notices.",
                "full_text": "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files.",
                "legal_code_url": "https://opensource.org/licenses/MIT",
                "is_default": False,
                "license_terms": [
                    {
                        "title": "Copyright Notice Required",
                        "title_ar": "إشعار حقوق الطبع والنشر مطلوب",
                        "description": "The above copyright notice and this permission notice shall be included in all copies.",
                        "description_ar": "يجب تضمين إشعار حقوق الطبع والنشر أعلاه وإشعار الإذن هذا في جميع النسخ.",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "label_ar": "الاستخدام التجاري",
                        "description": "You may use the material for commercial purposes.",
                        "description_ar": "يمكنك استخدام المواد لأغراض تجارية.",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "label_ar": "التعديل",
                        "description": "You may modify and adapt the material.",
                        "description_ar": "يمكنك تعديل وتكييف المواد.",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "label_ar": "التوزيع",
                        "description": "You may distribute the material.",
                        "description_ar": "يمكنك توزيع المواد.",
                    },
                    {
                        "key": "private_use",
                        "label": "Private use",
                        "label_ar": "الاستخدام الخاص",
                        "description": "You may use and modify the material in private.",
                        "description_ar": "يمكنك استخدام وتعديل المواد في خاص.",
                    },
                ],
                "conditions": [
                    {
                        "key": "include_copyright",
                        "label": "License and copyright notice",
                        "label_ar": "إشعار الترخيص وحقوق الطبع والنشر",
                        "description": "A copy of the license and copyright notice must be included.",
                        "description_ar": "يجب تضمين نسخة من الترخيص وإشعار حقوق الطبع والنشر.",
                    },
                ],
                "limitations": [
                    {
                        "key": "liability",
                        "label": "Liability",
                        "label_ar": "المسؤولية",
                        "description": "This license includes a limitation of liability.",
                        "description_ar": "يتضمن هذا الترخيص حدًا للمسؤولية.",
                    },
                    {
                        "key": "warranty",
                        "label": "Warranty",
                        "label_ar": "الضمان",
                        "description": "This license explicitly states that it does NOT provide any warranty.",
                        "description_ar": "ينص هذا الترخيص صراحة على أنه لا يوفر أي ضمان.",
                    },
                ],
            },
            {
                "code": "apache-2.0",
                "name": "Apache License 2.0",
                "short_name": "Apache 2.0",
                "url": "https://www.apache.org/licenses/LICENSE-2.0",
                "icon_url": "https://www.apache.org/foundation/press/kit/asf_logo.svg",
                "summary": "A permissive license that also provides an express grant of patent rights from contributors.",
                "full_text": "Licensed under the Apache License, Version 2.0. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0",
                "legal_code_url": "https://www.apache.org/licenses/LICENSE-2.0",
                "is_default": False,
                "license_terms": [
                    {
                        "title": "Copyright and License Notice Required",
                        "title_ar": "إشعار حقوق الطبع والنشر والترخيص مطلوب",
                        "description": "A copy of the license and copyright notice must be included with the software.",
                        "description_ar": "يجب تضمين نسخة من الترخيص وإشعار حقوق الطبع والنشر مع البرنامج.",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "label_ar": "الاستخدام التجاري",
                        "description": "You may use the material for commercial purposes.",
                        "description_ar": "يمكنك استخدام المواد لأغراض تجارية.",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "label_ar": "التعديل",
                        "description": "You may modify and adapt the material.",
                        "description_ar": "يمكنك تعديل وتكييف المواد.",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "label_ar": "التوزيع",
                        "description": "You may distribute the material.",
                        "description_ar": "يمكنك توزيع المواد.",
                    },
                    {
                        "key": "patent_use",
                        "label": "Patent use",
                        "label_ar": "استخدام براءة الاختراع",
                        "description": "This license provides an express grant of patent rights from contributors.",
                        "description_ar": "يوفر هذا الترخيص منحة صريحة لحقوق براءة الاختراع من المساهمين.",
                    },
                ],
                "conditions": [
                    {
                        "key": "include_copyright",
                        "label": "License and copyright notice",
                        "label_ar": "إشعار الترخيص وحقوق الطبع والنشر",
                        "description": "A copy of the license and copyright notice must be included.",
                        "description_ar": "يجب تضمين نسخة من الترخيص وإشعار حقوق الطبع والنشر.",
                    },
                    {
                        "key": "state_changes",
                        "label": "State changes",
                        "label_ar": "بيان التغييرات",
                        "description": "Changes made to the code must be documented.",
                        "description_ar": "يجب توثيق التغييرات المجراة على الكود.",
                    },
                ],
                "limitations": [
                    {
                        "key": "liability",
                        "label": "Liability",
                        "label_ar": "المسؤولية",
                        "description": "This license includes a limitation of liability.",
                        "description_ar": "يتضمن هذا الترخيص حدًا للمسؤولية.",
                    },
                    {
                        "key": "warranty",
                        "label": "Warranty",
                        "label_ar": "الضمان",
                        "description": "This license explicitly states that it does NOT provide any warranty.",
                        "description_ar": "ينص هذا الترخيص صراحة على أنه لا يوفر أي ضمان.",
                    },
                ],
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for license_data in default_licenses:
                code = license_data["code"]

                try:
                    license_obj, created = License.objects.get_or_create(
                        code=code,
                        defaults=license_data,
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ Created license: {license_obj.name}",
                            ),
                        )
                    elif force_update:
                        # Update existing license
                        for field, value in license_data.items():
                            setattr(license_obj, field, value)
                        license_obj.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"🔄 Updated license: {license_obj.name}",
                            ),
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠️  License already exists: {license_obj.name} (use --force to update)",
                            ),
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"❌ Error creating/updating license {code}: {e}",
                        ),
                    )
                    raise CommandError(f"Failed to create/update license {code}: {e}")

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("✅ License seeding completed!"))
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"   - Created: {created_count}")
        self.stdout.write(f"   - Updated: {updated_count}")
        self.stdout.write(f"   - Skipped: {skipped_count}")
        self.stdout.write(f"   - Total processed: {len(default_licenses)}")

        # Verify default license
        default_license = License.objects.filter(is_default=True).first()
        if default_license:
            self.stdout.write(f"🔒 Default license: {default_license.name}")
        else:
            self.stdout.write(self.style.ERROR("⚠️  No default license found!"))
