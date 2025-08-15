# AI Analysis Error Handling Improvements

## Overview

This document describes the improvements made to the AI analysis error handling system to address specific issues with error capture, database transactions, and user feedback.

## Issues Addressed

### 1. Error Capture and Logging
- **Problem**: AI service errors were not properly captured and logged
- **Solution**: Enhanced error handling with detailed logging in English
- **Implementation**: Added specific exception handling for different error types

### 2. Database Transaction Issues
- **Problem**: `PendingRollbackError` and `IntegrityError` when trying to save analysis results
- **Solution**: Proper transaction management with rollback and retry logic
- **Implementation**: Added specific handling for database constraint violations

### 3. Multiple AI Evaluations
- **Problem**: Database unique constraint prevented multiple analyses for the same task
- **Solution**: Check for existing analysis and update instead of insert
- **Implementation**: Added logic to update existing records instead of creating duplicates

### 4. Frontend Error Display
- **Problem**: Generic error messages not helpful to users
- **Solution**: Detailed error messages displayed as toast notifications
- **Implementation**: Enhanced error handling in frontend API calls

## Technical Implementation

### Backend Changes

#### 1. Analysis Service (`backend/service/analysis_service.py`)

**Key Improvements:**
- Added specific exception handling for `IntegrityError` and `PendingRollbackError`
- Implemented check for existing analysis records before insertion
- Enhanced error logging with detailed English messages
- Added proper transaction rollback handling
- Return error responses instead of throwing exceptions

**Error Handling Flow:**
```python
try:
    # AI service call
    analysis_report = await _call_ai_service(...)

    # Check for existing analysis
    existing_analysis = await db.execute(select(TaskAnalysis)...)

    if existing_analysis:
        # Update existing record
        update_stmt = update(TaskAnalysis).where(...)
        await db.execute(update_stmt)
    else:
        # Create new record
        analysis = TaskAnalysis(...)
        db.add(analysis)

    await db.commit()

except IntegrityError as e:
    # Handle duplicate entry error
    await db.rollback()
    # Try to update existing record
    # Return error response

except PendingRollbackError as e:
    # Handle session rollback error
    await db.rollback()
    # Try to save error with new session
    # Return error response

except Exception as e:
    # Handle other exceptions
    await db.rollback()
    # Save error to database
    # Return error response
```

#### 2. AI Service Call (`_call_ai_service`)

**Key Improvements:**
- Added timeout configuration (60 seconds)
- Enhanced error logging with specific error types
- Better error messages for different failure scenarios

**Error Types Handled:**
- `requests.exceptions.Timeout`: Network timeout errors
- `requests.exceptions.ConnectionError`: Connection failures
- `requests.exceptions.RequestException`: General request errors
- Invalid response format errors

#### 3. API Layer (`backend/api/api_analysis.py`)

**Key Improvements:**
- Enhanced error handling in API endpoints
- Proper error response formatting
- Detailed logging for debugging

### Frontend Changes

#### 1. Results Page (`frontend/src/pages/Results.tsx`)

**Key Improvements:**
- Enhanced error handling in `handleAnalysis` function
- Better error message extraction from API responses
- Improved user feedback with toast notifications

**Error Handling Flow:**
```typescript
try {
    const response = await analysisApi.analyzeTask(id);

    if (response.data?.status === 'error' || response.data?.status === 'failed') {
        const errorMessage = response.data?.error || response.data?.error_message;
        message.error(`AI summary failed: ${errorMessage}`);
        return;
    }

    // Handle success case

} catch (err: any) {
    // Extract error message from different sources
    let errorMessage = 'AI summary failed';

    if (err.data?.error) {
        errorMessage = err.data.error;
    } else if (err.data?.error_message) {
        errorMessage = err.data.error_message;
    } else if (err.message) {
        errorMessage = err.message;
    }

    message.error(`AI summary failed: ${errorMessage}`);
}
```

## Database Schema

The `test_insights` table has a unique constraint on `task_id`:
```sql
UNIQUE KEY `uk_task_id` (`task_id`)
```

This constraint is now properly handled by:
1. Checking for existing records before insertion
2. Using UPDATE instead of INSERT for existing tasks
3. Proper error handling for constraint violations

## Error Messages

### Backend Error Messages
- **Database Integrity Error**: "Analysis failed due to database constraint violation. Please try again."
- **Session Rollback Error**: "Analysis failed due to database transaction error. Please try again."
- **AI Service Timeout**: "AI service request timeout: {details}"
- **AI Service Connection Error**: "AI service connection error: {details}"
- **Invalid Response Format**: "Invalid response format from AI service - missing choices"

### Frontend Error Messages
- Displayed as toast notifications
- Extracted from API response error fields
- Fallback to generic messages if specific error not available

## Testing

A test script has been created (`backend/test_analysis_error_handling.py`) to verify:
- Network timeout error handling
- Database integrity error handling
- Session rollback error handling
- Successful analysis scenarios
- AI service call error scenarios

## Logging

All error scenarios are logged with detailed English messages:
- AI service configuration errors
- Database transaction errors
- AI service call failures
- Response format errors
- General exception handling

## Usage

### Multiple AI Evaluations
Users can now perform multiple AI analyses on the same task:
1. First analysis creates a new record
2. Subsequent analyses update the existing record
3. Latest analysis results always overwrite previous ones
4. No database constraint violations

### Error Feedback
Users receive detailed error messages via toast notifications:
- Network connectivity issues
- AI service configuration problems
- Database constraint violations
- General system errors

## Monitoring

The system now provides comprehensive logging for monitoring:
- All AI service calls are logged
- Database operations are tracked
- Error scenarios are captured with context
- Performance metrics are recorded

## Future Improvements

1. **Retry Logic**: Implement automatic retry for transient errors
2. **Circuit Breaker**: Add circuit breaker pattern for AI service calls
3. **Metrics**: Add metrics collection for error rates and response times
4. **Alerting**: Implement alerting for critical error scenarios
