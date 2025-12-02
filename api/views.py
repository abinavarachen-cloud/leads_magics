from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import *
from .serializers import *


# Create & List Campaigns
class CampaignListCreateView(generics.ListCreateAPIView):
    queryset = EmailCampaign.objects.all()
    serializer_class = EmailCampaignSerializer


# Retrieve / Update Campaign
class CampaignDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmailCampaign.objects.all()
    serializer_class = EmailCampaignSerializer


# SEND TEST EMAIL
class CampaignSendTestView(APIView):
    def post(self, request, pk):
        campaign = EmailCampaign.objects.get(pk=pk)

        serializer = CampaignSendTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["test_email"]

        # append to test emails
        if campaign.test_email_recipients:
            campaign.test_email_recipients += f",{email}"
        else:
            campaign.test_email_recipients = email

        campaign.status = "send_test_email"
        campaign.save()

        # campaign.send_test_emails()  # TODO: actual email sending

        return Response({"message": "Test email added & will be sent."})
        

# GENERATE RECIPIENTS FROM SELECTED LISTS
class CampaignGenerateRecipientsView(APIView):
    def post(self, request, pk):
        campaign = EmailCampaign.objects.get(pk=pk)

        # get contacts
        included = Contact.objects.filter(
            lists__in=campaign.contact_lists.all()
        ).distinct()

        excluded = Contact.objects.filter(
            lists__in=campaign.do_not_send_lists.all()
        )

        recipients = included.exclude(id__in=excluded)

        created = 0
        for contact in recipients:
            EmailRecipient.objects.get_or_create(
                campaign=campaign,
                contact=contact
            )
            created += 1

        return Response({
            "message": "Recipients generated",
            "total_created": created
        })
        

# SEND CAMPAIGN NOW
class CampaignSendNowView(APIView):
    def post(self, request, pk):
        campaign = EmailCampaign.objects.get(pk=pk)

        serializer = CampaignSendNowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['confirm'] is False:
            return Response({"error": "Please confirm"}, status=400)

        # generate recipients if not exists
        if campaign.recipients.count() == 0:
            # Generate automatically
            inc = Contact.objects.filter(lists__in=campaign.contact_lists.all()).distinct()
            exc = Contact.objects.filter(lists__in=campaign.do_not_send_lists.all())
            final = inc.exclude(id__in=exc)

            for c in final:
                EmailRecipient.objects.get_or_create(
                    campaign=campaign,
                    contact=c
                )

        # update status
        campaign.status = "sending"
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=["status", "sent_at"])

        # TODO: Queue celery jobs for batch sending
        return Response({"message": "Campaign scheduled for sending"})


# SCHEDULE CAMPAIGN
class CampaignScheduleView(APIView):
    def post(self, request, pk):
        campaign = EmailCampaign.objects.get(pk=pk)

        serializer = CampaignScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        campaign.status = "scheduled"
        campaign.scheduled_at = serializer.validated_data["scheduled_at"]
        campaign.save()

        return Response({"message": "Campaign scheduled"})





