"""
Serializers for License and AccessRequest models
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import AccessRequest
from .models import License

User = get_user_model()


class LicenseSerializer(serializers.ModelSerializer):
    """
    Serializer for License model with validation and status information
    """

    resource_title = serializers.CharField(source="resource.title", read_only=True)
    resource_type = serializers.CharField(
        source="resource.resource_type",
        read_only=True,
    )
    license_type_display = serializers.CharField(
        source="get_license_type_display",
        read_only=True,
    )
    is_effective = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    access_request_count = serializers.SerializerMethodField()

    class Meta:
        model = License
        fields = [
            "id",
            "resource",
            "resource_title",
            "resource_type",
            "license_type",
            "license_type_display",
            "terms",
            "geographic_restrictions",
            "usage_restrictions",
            "requires_approval",
            "is_effective",
            "is_expired",
            "effective_from",
            "expires_at",
            "days_until_expiry",
            "access_request_count",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "resource_title",
            "resource_type",
            "license_type_display",
            "is_effective",
            "is_expired",
            "days_until_expiry",
            "access_request_count",
            "created_at",
            "updated_at",
        ]

    def get_is_effective(self, obj):
        """Check if license is currently effective"""
        return obj.is_effective()

    def get_is_expired(self, obj):
        """Check if license has expired"""
        return obj.is_expired()

    def get_days_until_expiry(self, obj):
        """Get days until license expires"""
        return obj.days_until_expiry()

    def get_access_request_count(self, obj):
        """Get count of access requests governed by this license"""
        # This is a simplified count - in reality, access requests are linked to distributions
        return (
            obj.resource.distributions.filter(
                access_requests__is_active=True,
            )
            .distinct()
            .count()
        )

    def validate_license_type(self, value):
        """Validate license type"""
        valid_types = ["open", "restricted", "commercial"]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"License type must be one of: {', '.join(valid_types)}",
            )
        return value

    def validate_geographic_restrictions(self, value):
        """Validate geographic restrictions structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError(
                "Geographic restrictions must be a JSON object",
            )

        if value:
            # Validate allowed/restricted countries format
            allowed = value.get("allowed_countries", [])
            restricted = value.get("restricted_countries", [])

            if allowed and not isinstance(allowed, list):
                raise serializers.ValidationError("Allowed countries must be a list")

            if restricted and not isinstance(restricted, list):
                raise serializers.ValidationError("Restricted countries must be a list")

            # Validate country codes (basic validation)
            all_countries = allowed + restricted
            for country in all_countries:
                if not isinstance(country, str) or len(country) != 2:
                    raise serializers.ValidationError(
                        f"Invalid country code '{country}'. Must be 2-letter ISO code",
                    )

        return value or {}

    def validate_usage_restrictions(self, value):
        """Validate usage restrictions structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError(
                "Usage restrictions must be a JSON object",
            )

        if value:
            # Validate rate limits
            if "rate_limits" in value:
                rate_limits = value["rate_limits"]
                if not isinstance(rate_limits, dict):
                    raise serializers.ValidationError("Rate limits must be an object")

                valid_rate_fields = [
                    "requests_per_minute",
                    "requests_per_hour",
                    "requests_per_day",
                ]
                for field, limit in rate_limits.items():
                    if field not in valid_rate_fields:
                        raise serializers.ValidationError(
                            f"Invalid rate limit field '{field}'",
                        )
                    if not isinstance(limit, int) or limit < 0:
                        raise serializers.ValidationError(
                            f"Rate limit '{field}' must be a non-negative integer",
                        )

            # Validate attribution requirements
            if "requires_attribution" in value:
                if not isinstance(value["requires_attribution"], bool):
                    raise serializers.ValidationError(
                        "Requires attribution must be boolean",
                    )

            if "attribution_text" in value:
                if not isinstance(value["attribution_text"], str):
                    raise serializers.ValidationError(
                        "Attribution text must be a string",
                    )

        return value or {}

    def validate(self, attrs):
        """Cross-field validation"""
        effective_from = attrs.get("effective_from")
        expires_at = attrs.get("expires_at")

        # Validate date range
        if effective_from and expires_at:
            if expires_at <= effective_from:
                raise serializers.ValidationError(
                    "Expiry date must be after effective date",
                )

        # Validate effective date is not in the past (for new licenses)
        if not self.instance and effective_from:
            if effective_from < timezone.now():
                raise serializers.ValidationError(
                    "Effective date cannot be in the past",
                )

        return attrs


class AccessRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for AccessRequest model with workflow information
    """

    requester_name = serializers.CharField(
        source="requester.get_full_name",
        read_only=True,
    )
    requester_email = serializers.CharField(source="requester.email", read_only=True)
    distribution_info = serializers.SerializerMethodField()
    resource_info = serializers.SerializerMethodField()
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name",
        read_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )
    rejection_reason_display = serializers.CharField(
        source="get_rejection_reason_display",
        read_only=True,
    )
    is_expired = serializers.SerializerMethodField()
    is_access_valid = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    can_be_reviewed = serializers.SerializerMethodField()
    can_be_revoked = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "requester",
            "requester_name",
            "requester_email",
            "distribution",
            "distribution_info",
            "resource_info",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "justification",
            "admin_notes",
            "rejection_reason",
            "rejection_reason_display",
            "approved_by",
            "approved_by_name",
            "notification_sent",
            "is_expired",
            "is_access_valid",
            "can_be_reviewed",
            "can_be_revoked",
            "requested_at",
            "reviewed_at",
            "expires_at",
            "days_until_expiry",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requester_name",
            "requester_email",
            "distribution_info",
            "resource_info",
            "approved_by_name",
            "status_display",
            "is_expired",
            "is_access_valid",
            "requested_at",
            "reviewed_at",
            "days_until_expiry",
            "created_at",
            "updated_at",
        ]

    def get_distribution_info(self, obj):
        """Get distribution information"""
        return {
            "id": obj.distribution.id,
            "format_type": obj.distribution.format_type,
            "version": obj.distribution.version,
            "endpoint_url": obj.distribution.endpoint_url,
        }

    def get_resource_info(self, obj):
        """Get resource information"""
        resource = obj.distribution.resource
        return {
            "id": resource.id,
            "title": resource.title,
            "resource_type": resource.resource_type,
            "language": resource.language,
        }

    def get_is_expired(self, obj):
        """Check if approved access has expired"""
        return obj.is_expired()

    def get_is_access_valid(self, obj):
        """Check if access is currently valid"""
        return obj.is_access_valid()

    def get_days_until_expiry(self, obj):
        """Get days until access expires"""
        return obj.days_until_expiry()

    def get_can_be_reviewed(self, obj):
        """Check if request can be reviewed"""
        return obj.can_be_reviewed()

    def get_can_be_revoked(self, obj):
        """Check if request can be revoked"""
        return obj.can_be_revoked()

    def validate_requester(self, value):
        """Validate requester has Developer role"""
        if value and not value.is_developer():
            raise serializers.ValidationError(
                "Requester must have Developer role",
            )
        return value

    def validate_status(self, value):
        """Validate status transitions"""
        valid_statuses = [
            "pending",
            "under_review",
            "approved",
            "rejected",
            "expired",
            "revoked",
        ]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(valid_statuses)}",
            )

        # Validate status transitions
        if self.instance:
            current_status = self.instance.status

            # Define valid transitions
            valid_transitions = {
                "pending": ["under_review", "approved", "rejected"],
                "under_review": ["approved", "rejected"],
                "approved": ["revoked", "expired"],
                "rejected": [],  # Terminal state
                "expired": [],  # Terminal state
                "revoked": [],  # Terminal state
            }

            if value not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Invalid status transition from '{current_status}' to '{value}'",
                )

        return value

    def validate_justification(self, value):
        """Validate justification is provided and meaningful"""
        if not value or len(value.strip()) < 50:
            raise serializers.ValidationError(
                "Justification must be at least 50 characters long",
            )
        return value.strip()

    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure unique request per requester/distribution
        requester = attrs.get("requester") or (self.instance.requester if self.instance else None)
        distribution = attrs.get("distribution") or (self.instance.distribution if self.instance else None)

        if requester and distribution:
            existing_qs = AccessRequest.objects.filter(
                requester=requester,
                distribution=distribution,
                is_active=True,
            )

            # Exclude current instance if updating
            if self.instance:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)

            if existing_qs.exists():
                raise serializers.ValidationError(
                    "An active access request already exists for this requester and distribution",
                )

        return attrs

    def create(self, validated_data):
        """Create access request with auto-set requester"""
        # Auto-set requester to current user if not provided
        if "requester" not in validated_data:
            validated_data["requester"] = self.context["request"].user

        return super().create(validated_data)


class AccessRequestApprovalSerializer(serializers.ModelSerializer):
    """
    Serializer for approving/rejecting access requests
    """

    action = serializers.ChoiceField(
        choices=["approve", "reject"],
        write_only=True,
        required=True,
    )
    expires_at = serializers.DateTimeField(
        required=False,
        help_text="When the approved access should expire (only for approve action)",
    )

    class Meta:
        model = AccessRequest
        fields = ["action", "admin_notes", "expires_at"]

    def validate_expires_at(self, value):
        """Validate expiry date is in the future"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future")
        return value

    def validate(self, attrs):
        """Validate approval/rejection data"""
        action = attrs.get("action")

        # Ensure access request is pending
        if self.instance.status != "pending":
            raise serializers.ValidationError(
                f"Cannot {action} request with status '{self.instance.status}'",
            )

        # For approval, validate expiry date
        if action == "approve":
            expires_at = attrs.get("expires_at")
            if not expires_at:
                # Default to 1 year from now
                from datetime import timedelta

                attrs["expires_at"] = timezone.now() + timedelta(days=365)

        return attrs

    def save(self):
        """Approve or reject the access request"""
        action = self.validated_data["action"]
        admin_notes = self.validated_data.get("admin_notes", "")
        admin_user = self.context["request"].user

        if action == "approve":
            expires_at = self.validated_data.get("expires_at")
            self.instance.approve(
                admin_user=admin_user,
                expires_at=expires_at,
                admin_notes=admin_notes,
            )
        else:  # reject
            self.instance.reject(
                admin_user=admin_user,
                admin_notes=admin_notes,
            )

        return self.instance


class AccessRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for access request listings
    """

    requester_name = serializers.CharField(
        source="requester.get_full_name",
        read_only=True,
    )
    resource_title = serializers.CharField(
        source="distribution.resource.title",
        read_only=True,
    )
    distribution_format = serializers.CharField(
        source="distribution.format_type",
        read_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "requester_name",
            "resource_title",
            "distribution_format",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "requested_at",
            "reviewed_at",
        ]


class AccessRequestWorkflowSerializer(serializers.ModelSerializer):
    """
    Serializer for workflow actions (start review, approve, reject, revoke)
    """

    action = serializers.ChoiceField(
        choices=["start_review", "approve", "reject", "revoke"],
        write_only=True,
        required=True,
    )
    expires_at = serializers.DateTimeField(
        required=False,
        help_text="When the approved access should expire (only for approve action)",
    )
    rejection_reason = serializers.ChoiceField(
        choices=[
            ("insufficient_justification", "Insufficient Justification"),
            ("license_violation", "License Terms Violation"),
            ("incomplete_information", "Incomplete Information"),
            ("policy_violation", "Policy Violation"),
            ("resource_unavailable", "Resource Unavailable"),
            ("other", "Other"),
        ],
        required=False,
        help_text="Reason for rejection (only for reject action)",
    )

    class Meta:
        model = AccessRequest
        fields = ["action", "admin_notes", "expires_at", "rejection_reason"]

    def validate_expires_at(self, value):
        """Validate expiry date is in the future"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future")
        return value

    def validate(self, attrs):
        """Validate workflow action data"""
        action = attrs.get("action")

        # Validate request can be acted upon
        if action in ["start_review", "approve", "reject"] and not self.instance.can_be_reviewed():
            raise serializers.ValidationError(
                f"Cannot {action} request with status '{self.instance.status}'",
            )

        if action == "revoke" and not self.instance.can_be_revoked():
            raise serializers.ValidationError(
                f"Cannot revoke request with status '{self.instance.status}'",
            )

        # For approval, set default expiry date if not provided
        if action == "approve":
            expires_at = attrs.get("expires_at")
            if not expires_at:
                # Default to 1 year from now
                from datetime import timedelta

                attrs["expires_at"] = timezone.now() + timedelta(days=365)

        # For rejection, require rejection reason
        if action == "reject" and not attrs.get("rejection_reason"):
            attrs["rejection_reason"] = "other"

        return attrs

    def save(self):
        """Execute the workflow action"""
        action = self.validated_data["action"]
        admin_notes = self.validated_data.get("admin_notes", "")
        admin_user = self.context["request"].user

        if action == "start_review":
            self.instance.start_review(admin_user=admin_user, admin_notes=admin_notes)
        elif action == "approve":
            expires_at = self.validated_data.get("expires_at")
            self.instance.approve(
                admin_user=admin_user,
                expires_at=expires_at,
                admin_notes=admin_notes,
            )
        elif action == "reject":
            rejection_reason = self.validated_data.get("rejection_reason", "")
            self.instance.reject(
                admin_user=admin_user,
                rejection_reason=rejection_reason,
                admin_notes=admin_notes,
            )
        elif action == "revoke":
            self.instance.revoke(admin_user=admin_user, admin_notes=admin_notes)

        return self.instance


class BulkAccessRequestActionSerializer(serializers.Serializer):
    """
    Serializer for bulk actions on access requests
    """

    request_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        help_text="List of access request IDs to process",
    )
    action = serializers.ChoiceField(
        choices=["approve", "reject", "start_review"],
        required=True,
    )
    admin_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Admin notes for all requests",
    )
    expires_at = serializers.DateTimeField(
        required=False,
        help_text="Expiry date for approved requests",
    )
    rejection_reason = serializers.ChoiceField(
        choices=[
            ("insufficient_justification", "Insufficient Justification"),
            ("license_violation", "License Terms Violation"),
            ("incomplete_information", "Incomplete Information"),
            ("policy_violation", "Policy Violation"),
            ("resource_unavailable", "Resource Unavailable"),
            ("other", "Other"),
        ],
        required=False,
        help_text="Reason for rejection",
    )

    def validate_expires_at(self, value):
        """Validate expiry date is in the future"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future")
        return value

    def validate(self, attrs):
        """Validate bulk action data"""
        action = attrs.get("action")

        # Set defaults
        if action == "approve" and not attrs.get("expires_at"):
            from datetime import timedelta

            attrs["expires_at"] = timezone.now() + timedelta(days=365)

        if action == "reject" and not attrs.get("rejection_reason"):
            attrs["rejection_reason"] = "other"

        return attrs
