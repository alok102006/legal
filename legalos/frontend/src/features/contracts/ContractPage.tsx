import React from 'react';
import { useParams } from 'react-router-dom';
import { ReadingRoom } from './ReadingRoom';

/** /contracts/:id: the same reading room with this contract open. */
export const ContractPage: React.FC = () => {
  const { id } = useParams();
  return <ReadingRoom selectedId={id} />;
};
