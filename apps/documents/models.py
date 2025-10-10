from django.db import models
import uuid

class BrokerDocument(models.Model):
    """
    Stores metadata for uploaded broker research PDFs.
    LlamaIndex handles the actual vector embeddings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='pdfs/')
    
    # Document metadata
    broker = models.CharField(max_length=200, help_text="e.g., UBS, Barclays, Goldman Sachs", blank=True, null=True)
    ticker = models.CharField(max_length=20, help_text="e.g., NVDA, AAPL, TSLA", blank=True, null=True)
    report_date = models.DateField(blank=True, null=True)
    title = models.CharField(max_length=500, blank=True)
    
    # File hash for duplicate detection
    file_hash = models.CharField(max_length=64, unique=True, help_text="SHA256 hash of the file content", blank=True, null=True)
    
    # Processing status
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    # Statistics
    total_pages = models.IntegerField(default=0)
    total_chunks = models.IntegerField(default=0)
    total_tables = models.IntegerField(default=0)
    total_images = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-report_date', '-created_at']
        verbose_name = "Broker Document"
        verbose_name_plural = "Broker Documents"
    
    def __str__(self):
        return f"{self.broker} - {self.ticker} ({self.report_date})"