import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the control center shell', async () => {
    render(<App />);

    expect(await screen.findByText('open collar')).toBeInTheDocument();
    expect(await screen.findByText('Run history')).toBeInTheDocument();
    expect(await screen.findByText('Inspector')).toBeInTheDocument();
    expect(await screen.findByText('Prompt')).toBeInTheDocument();
  });
});
