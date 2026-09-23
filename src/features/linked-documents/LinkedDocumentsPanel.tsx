import React, { useRef, useState } from 'react';
import { useLinkedDocuments, OwnerType } from './useLinkedDocuments';
import { useGlobalMessages } from '../../app/AppShell';
import { useDeleteActions } from '../../hooks/useDeleteActions';

interface Props {
  ownerType: OwnerType;
  ownerId: number;
}

export function LinkedDocumentsPanel({ ownerType, ownerId }: Props) {
  const { documents, isLoading, error, addDocuments, deleteDocument, downloadDocumentUrl } = useLinkedDocuments(ownerType, ownerId);
  const { showMessage } = useGlobalMessages();
  const showDeleteActions = useDeleteActions();
  
  const [isUploading, setIsUploading] = useState(false);
  const [manualId, setManualId] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      const docsToWrite = await Promise.all(
        Array.from(files).map(async (file) => {
          return new Promise<any>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const base64 = (reader.result as string).split(',')[1];
              resolve({
                filename: file.name,
                content_type: file.type,
                content_base64: base64
              });
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
          });
        })
      );
      
      await addDocuments(docsToWrite);
      showMessage({ type: 'success', text: `${files.length} Dokument(e) hochgeladen.` });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Upload fehlgeschlagen: ${err.message}` });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleManualLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualId.trim()) return;

    setIsUploading(true);
    try {
      await addDocuments([{
        paperless_document_id: manualId.trim()
      }]);
      showMessage({ type: 'success', text: `Paperless Dokument ID ${manualId} verknüpft.` });
      setManualId('');
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler beim Verknüpfen: ${err.message}` });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (docId: number) => {
    if (!window.confirm('Dokument-Verknüpfung wirklich löschen?')) return;
    try {
      await deleteDocument(docId);
      showMessage({ type: 'success', text: 'Dokument entfernt.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler beim Löschen: ${err.message}` });
    }
  };

  if (isLoading) return <div>Lade Dokumente...</div>;
  if (error) return <div className="message error">Fehler beim Laden der Dokumente</div>;

  return (
    <div className="linked-documents">
      <h4>Dokumente</h4>
      
      {documents.length > 0 ? (
        <ul className="document-list" style={{ listStyle: 'none', padding: 0, marginBottom: '1rem' }}>
          {documents.map(doc => (
            <li key={doc.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid #eee' }}>
              <div>
                <a 
                  href={doc.paperless_reference_url || downloadDocumentUrl(doc.id)} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{ fontWeight: 'bold' }}
                >
                  {doc.filename || `Paperless ID ${doc.paperless_document_id}`}
                </a>
                <span style={{ fontSize: '0.85em', color: '#666', marginLeft: '0.5rem' }}>
                  ({doc.upload_status})
                </span>
              </div>
              {showDeleteActions && <button onClick={() => handleDelete(doc.id)} className="button button-small button-outline">
                Löschen
              </button>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">Keine Dokumente verknüpft.</p>
      )}

      <div className="document-actions" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
        <div>
          <input 
            type="file" 
            multiple 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            style={{ display: 'none' }} 
          />
          <button 
            type="button" 
            className="button" 
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? 'Lädt hoch...' : 'Datei(en) hochladen'}
          </button>
        </div>

        <form onSubmit={handleManualLink} style={{ display: 'flex', gap: '0.5rem' }}>
          <input 
            type="text" 
            placeholder="Paperless ID" 
            value={manualId}
            onChange={e => setManualId(e.target.value)}
            className="input"
            style={{ width: '120px' }}
          />
          <button type="submit" className="button button-outline" disabled={!manualId.trim() || isUploading}>
            Verknüpfen
          </button>
        </form>
      </div>
    </div>
  );
}
