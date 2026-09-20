import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type DocumentResponse = components['schemas']['DocumentResponse'];
type DocumentWrite = components['schemas']['DocumentWrite'];

export type OwnerType = 'expenses' | 'tenants' | 'leases';

export function useLinkedDocuments(ownerType: OwnerType, ownerId: number) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.GET(`/api/v1/{owner_type}/{owner_id}/documents`, {
        params: { path: { owner_type: ownerType, owner_id: ownerId } }
      });
      if (res.data?.documents) {
        setDocuments(res.data.documents);
      }
    } catch (err: any) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, [ownerType, ownerId]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const addDocuments = async (docs: DocumentWrite[]) => {
    const res = await apiClient.POST(`/api/v1/{owner_type}/{owner_id}/documents`, {
      params: { path: { owner_type: ownerType, owner_id: ownerId } },
      body: { documents: docs }
    });
    // API returns DocumentListResponse
    if (res.data?.documents) {
      setDocuments(res.data.documents);
    }
    return res;
  };

  const deleteDocument = async (documentId: number) => {
    const res = await apiClient.DELETE(`/api/v1/{owner_type}/{owner_id}/documents/{document_id}`, {
      params: { path: { owner_type: ownerType, owner_id: ownerId, document_id: documentId } }
    });
    if (res.data?.deleted) {
      setDocuments(prev => prev.filter(d => d.id !== documentId));
    }
    return res;
  };

  const downloadDocumentUrl = (documentId: number) => {
    return `/api/v1/${ownerType}/${ownerId}/documents/${documentId}/download`;
  };

  return {
    documents,
    isLoading,
    error,
    refresh: fetchDocuments,
    addDocuments,
    deleteDocument,
    downloadDocumentUrl
  };
}
