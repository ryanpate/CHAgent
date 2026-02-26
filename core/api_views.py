from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class EmailTokenObtainPairSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('No active account found with the given credentials')

        if not user.check_password(password):
            raise serializers.ValidationError('No active account found with the given credentials')

        if not user.is_active:
            raise serializers.ValidationError('No active account found with the given credentials')

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class EmailTokenObtainPairView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError:
            return Response(
                {'detail': 'No active account found with the given credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(serializer.validated_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    from core.models import NativePushToken

    token = request.data.get('token')
    platform = request.data.get('platform')
    device_name = request.data.get('device_name', '')

    if not token or platform not in ('ios', 'android'):
        return Response(
            {'error': 'token and platform (ios/android) are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    obj, created = NativePushToken.objects.update_or_create(
        user=request.user,
        token=token,
        defaults={
            'organization': request.organization,
            'platform': platform,
            'device_name': device_name,
            'is_active': True,
        },
    )
    return Response(
        {'status': 'created' if created else 'updated'},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unregister_push_token(request):
    from core.models import NativePushToken

    token = request.data.get('token')
    if not token:
        return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

    deleted, _ = NativePushToken.objects.filter(user=request.user, token=token).delete()
    if deleted:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response({'error': 'token not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_badge_count(request):
    from core.models import NativePushToken

    NativePushToken.objects.filter(user=request.user).update(unread_badge_count=0)
    return Response({'status': 'cleared'})
