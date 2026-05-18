from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class InvoiceStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'Belum Lunas'
    PAID = 'PAID', 'Lunas'
    OVERDUE = 'OVERDUE', 'Jatuh Tempo'
    REFUNDED = 'REFUNDED', 'Dikembalikan'


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', 'Transfer Bank'
    EWALLET = 'EWALLET', 'E-Wallet'
    CARD = 'CARD', 'Kartu'
    CASH = 'CASH', 'Tunai'


class PaymentGateway(models.TextChoices):
    MIDTRANS = 'MIDTRANS', 'Midtrans'
    XENDIT = 'XENDIT', 'Xendit'
    MANUAL = 'MANUAL', 'Manual'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Tertunda'
    SUCCESS = 'SUCCESS', 'Berhasil'
    FAILED = 'FAILED', 'Gagal'


class RefundStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', 'Diminta'
    APPROVED = 'APPROVED', 'Disetujui'
    REJECTED = 'REJECTED', 'Ditolak'
    PROCESSED = 'PROCESSED', 'Diproses'


def _generate_invoice_number():
    from django.utils import timezone
    year = timezone.now().year
    last = (
        Invoice.objects
        .filter(invoice_number__startswith=f'INV-{year}-')
        .order_by('-invoice_number')
        .first()
    )
    if last:
        try:
            seq = int(last.invoice_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'INV-{year}-{seq:05d}'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.PROTECT,
        related_name='invoices',
        db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='IDR')
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.UNPAID,
        db_index=True,
    )
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Faktur'
        verbose_name_plural = 'Faktur'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['status']),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            with transaction.atomic():
                self.invoice_number = _generate_invoice_number()
        amount = Decimal(self.amount or 0)
        tax = Decimal(self.tax_amount or 0)
        disc = Decimal(self.discount_amount or 0)
        self.total_amount = amount + tax - disc
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number or f'Invoice #{self.pk}'


class Payment(models.Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='payments', db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices)
    gateway = models.CharField(
        max_length=15, choices=PaymentGateway.choices, default=PaymentGateway.MANUAL,
    )
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pembayaran'
        verbose_name_plural = 'Pembayaran'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Payment for {self.invoice} — {self.amount}'


class Refund(models.Model):
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name='refunds', db_index=True,
    )
    # Denormalized for convenience
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='refunds', db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(
        max_length=10, choices=RefundStatus.choices, default=RefundStatus.REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_requests',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_approvals',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    gateway_refund_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengembalian Dana'
        verbose_name_plural = 'Pengembalian Dana'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment']),
            models.Index(fields=['status']),
        ]

    def clean(self):
        super().clean()
        if self.payment_id and self.amount and self.amount > self.payment.amount:
            raise ValidationError({
                'amount': 'Refund amount tidak boleh melebihi nilai pembayaran asli.'
            })

    def __str__(self):
        return f'Refund {self.amount} — {self.payment}'
