import React from 'react';
import { useParams } from 'react-router-dom';
import { NoticesWorkspace } from './Workspace';

export const NoticePage: React.FC = () => {
  const { id } = useParams();
  return <NoticesWorkspace id={id} />;
};
