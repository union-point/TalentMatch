import { Link } from 'react-router-dom';

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="TalentMatch home">
      <img src="/favicon.svg" alt="" width="36" height="36" />
      TalentMatch
    </Link>
  );
}
