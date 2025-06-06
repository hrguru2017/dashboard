# daily_submission_dashboard/main.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename 
import pandas as pd 
import os 
from datetime import date, datetime, timezone 
import calendar 
from sqlalchemy import func 

from models import SubmissionBatch, Profile, User 
from extensions import db
from forms import SubmissionForm, MonthYearSelectionForm, UserCreationForm, EditProfileForm 

main_bp = Blueprint('main', __name__)

EXPECTED_EXCEL_COLUMNS = {
    "date_col": "Date",
    "position_col": "Position",
    "client_col": "Client",
    "candidate_name_col": "Candidate Name",
    "contact_number_col": "Contact Number",
    "email_id_col": "Email ID",
    "total_experience_col": "Total Experience",
    "current_ctc_col": "Current CTC",
    "expected_ctc_col": "ECTC",
    "notice_period_col": "Notice Period",
    "feedback_col": "Feedback"
}

PROFILES_PER_PAGE = 20 

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    user_submissions_display = [] 
    current_month_total_display = 0 

    if current_user.role == 'manager':
        batches = SubmissionBatch.query.order_by(SubmissionBatch.processed_timestamp.desc()).limit(10).all()
        user_submissions_display = batches 
        
        now_dt = datetime.now(timezone.utc)
        if db.engine.name == 'sqlite':
            current_month_sum_obj = db.session.query(func.sum(SubmissionBatch.number_of_profiles))\
                                .filter(func.strftime('%Y-%m', SubmissionBatch.submission_date) == now_dt.strftime('%Y-%m'))\
                                .scalar()
        else: 
            current_month_sum_obj = db.session.query(func.sum(SubmissionBatch.number_of_profiles))\
                                .filter(db.extract('year', SubmissionBatch.submission_date) == now_dt.year)\
                                .filter(db.extract('month', SubmissionBatch.submission_date) == now_dt.month)\
                                .scalar()
        current_month_total_display = current_month_sum_obj if current_month_sum_obj is not None else 0
        
    else: 
        batches = SubmissionBatch.query.filter_by(user_id=current_user.id)\
                                     .order_by(SubmissionBatch.processed_timestamp.desc())\
                                     .limit(10).all()
        user_submissions_display = batches

    return render_template('dashboard.html', 
                           title='Dashboard', 
                           submissions=user_submissions_display, 
                           current_month_total=current_month_total_display)


@main_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def create_submission():
    form = SubmissionForm()
    if form.validate_on_submit():
        submission_date_from_form = form.submission_date.data
        file = form.profile_sheet.data 

        if not file or not file.filename:
            flash("No file selected for upload.", "warning")
            return render_template('create_submission.html', title='Upload Profile Sheet', form=form)

        original_filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], original_filename)
        
        try:
            file.save(filepath) 

            try:
                df = pd.read_excel(filepath, engine='openpyxl')
            except Exception as e:
                flash(f"Error reading Excel file: {e}. Please ensure it's a valid .xlsx file and column names match.", 'danger')
                current_app.logger.error(f"Excel read error for {original_filename} by user {current_user.id}: {e}")
                if os.path.exists(filepath): os.remove(filepath) 
                return render_template('create_submission.html', title='Upload Profile Sheet', form=form)

            if df.empty:
                flash("The uploaded Excel file is empty or has no data rows.", 'warning')
                if os.path.exists(filepath): os.remove(filepath) 
                return render_template('create_submission.html', title='Upload Profile Sheet', form=form)

            actual_excel_columns = df.columns.tolist()
            missing_cols = [expected_name for key, expected_name in EXPECTED_EXCEL_COLUMNS.items() if expected_name not in actual_excel_columns]
            if missing_cols:
                flash(f"Excel file missing required columns: {', '.join(missing_cols)}. Please check your file headers.", 'danger')
                if os.path.exists(filepath): os.remove(filepath) 
                return render_template('create_submission.html', title='Upload Profile Sheet', form=form)

            submission_batch = SubmissionBatch(
                submission_date=submission_date_from_form,
                user_id=current_user.id,
                uploaded_filename=original_filename
            )
            
            profiles_to_add_to_batch_list = []
            skipped_duplicates_info = []
            successfully_added_count = 0

            def get_str_val(row_data, col_key_in_dict):
                excel_col_name = EXPECTED_EXCEL_COLUMNS[col_key_in_dict]
                val = row_data.get(excel_col_name)
                return str(val).strip() if pd.notna(val) and str(val).strip() else None

            for index, row in df.iterrows():
                candidate_name = get_str_val(row, "candidate_name_col")
                email_id = get_str_val(row, "email_id_col")
                
                is_duplicate = False
                if candidate_name and email_id: 
                    existing_profile = Profile.query.filter(
                        func.lower(Profile.candidate_name) == func.lower(candidate_name),
                        func.lower(Profile.email_id) == func.lower(email_id)
                    ).first()
                    if existing_profile:
                        is_duplicate = True
                        skipped_duplicates_info.append(f"'{candidate_name}' (Email: {email_id})")
                elif not candidate_name or not email_id:
                    skipped_duplicates_info.append(f"Row {index + 2} (missing name/email)")
                    continue 

                if is_duplicate:
                    current_app.logger.info(f"Skipping duplicate profile: {candidate_name}, {email_id} from file {original_filename}")
                    continue 

                profile_date_val = row.get(EXPECTED_EXCEL_COLUMNS["date_col"])
                activity_date = None
                if pd.notna(profile_date_val):
                    if isinstance(profile_date_val, datetime):
                        activity_date = profile_date_val.date()
                    elif isinstance(profile_date_val, date):
                        activity_date = profile_date_val
                    else:
                        try:
                            activity_date = pd.to_datetime(str(profile_date_val)).date()
                        except ValueError:
                            current_app.logger.warning(f"Could not parse date '{profile_date_val}' for profile '{candidate_name}'. Setting to None.")
                            activity_date = None
                
                feedback_text = get_str_val(row, "feedback_col")

                profile = Profile(
                    profile_activity_date=activity_date,
                    position=get_str_val(row, "position_col"),
                    client=get_str_val(row, "client_col"),
                    candidate_name=candidate_name,
                    contact_number=get_str_val(row, "contact_number_col"),
                    email_id=email_id,
                    total_experience=get_str_val(row, "total_experience_col"),
                    current_ctc=get_str_val(row, "current_ctc_col"),
                    expected_ctc=get_str_val(row, "expected_ctc_col"),
                    notice_period=get_str_val(row, "notice_period_col"),
                    feedback=feedback_text
                )
                profiles_to_add_to_batch_list.append(profile)
                successfully_added_count += 1
            
            if successfully_added_count > 0:
                submission_batch.number_of_profiles = successfully_added_count
                submission_batch.profiles.extend(profiles_to_add_to_batch_list)
                db.session.add(submission_batch)
                db.session.commit()
                
                flash_message = f'{successfully_added_count} new profiles from "{original_filename}" were uploaded for {submission_date_from_form.strftime("%B %d, %Y")}!'
                if skipped_duplicates_info:
                    skipped_message = "; ".join(skipped_duplicates_info[:3]) 
                    flash_message += f" Skipped {len(skipped_duplicates_info)} duplicate or incomplete profiles (e.g., {skipped_message}"
                    if len(skipped_duplicates_info) > 3:
                        flash_message += " and more)."
                    else:
                        flash_message += ")."
                flash(flash_message, 'success')
            else: 
                flash_message = f'No new profiles were uploaded from "{original_filename}".'
                if skipped_duplicates_info:
                    skipped_message = "; ".join(skipped_duplicates_info[:3])
                    flash_message += f" All {len(skipped_duplicates_info)} profiles were duplicates or had incomplete key info (e.g., {skipped_message}"
                    if len(skipped_duplicates_info) > 3:
                         flash_message += " and more)."
                    else:
                        flash_message += ")."
                else:
                    flash_message += " The file might have been empty of valid data after the header row."
                flash(flash_message, 'warning')
            
            return redirect(url_for('main.dashboard'))

        except Exception as e: 
            db.session.rollback()
            flash(f'An unexpected error occurred during file processing: {e}', 'danger')
            current_app.logger.error(f"Unhandled error processing file {original_filename} for user {current_user.id}: {e}", exc_info=True)
            if 'filepath' in locals() and os.path.exists(filepath): 
                 try:
                     os.remove(filepath)
                 except OSError as rm_e:
                     current_app.logger.error(f"Error deleting uploaded file {filepath} after unhandled error: {rm_e}")
            
    return render_template('create_submission.html', 
                           title='Upload Profile Sheet', 
                           form=form)


@main_bp.route('/report/monthly', methods=['GET', 'POST'])
@login_required
def monthly_report():
    if current_user.role != 'manager':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.dashboard'))

    form = MonthYearSelectionForm()
    report_data = None # Initialize to ensure it's always passed, even if form not submitted

    if form.validate_on_submit(): 
        year = form.year.data
        month = form.month.data
        
        month_name = calendar.month_name[month]
        period_display_name = f"{month_name} {year}"
        query_filter_year_month = f"{year:04d}-{month:02d}"

        # --- Total Profiles Calculation ---
        if db.engine.name == 'sqlite':
            total_profiles_in_period = db.session.query(func.sum(SubmissionBatch.number_of_profiles))\
                                    .filter(func.strftime('%Y-%m', SubmissionBatch.submission_date) == query_filter_year_month)\
                                    .scalar()
        else: 
            total_profiles_in_period = db.session.query(func.sum(SubmissionBatch.number_of_profiles))\
                                    .filter(db.extract('year', SubmissionBatch.submission_date) == year)\
                                    .filter(db.extract('month', SubmissionBatch.submission_date) == month)\
                                    .scalar()
        total_profiles_count = total_profiles_in_period if total_profiles_in_period is not None else 0

        # --- Detailed Profiles List ---
        if db.engine.name == 'sqlite':
            profiles_list_for_period = Profile.query \
                .join(SubmissionBatch, Profile.submission_batch_id == SubmissionBatch.id) \
                .filter(func.strftime('%Y-%m', SubmissionBatch.submission_date) == query_filter_year_month) \
                .order_by(SubmissionBatch.submission_date.asc(), Profile.id.asc()) \
                .all()
        else: 
            profiles_list_for_period = Profile.query \
                .join(SubmissionBatch, Profile.submission_batch_id == SubmissionBatch.id) \
                .filter(db.extract('year', SubmissionBatch.submission_date) == year) \
                .filter(db.extract('month', SubmissionBatch.submission_date) == month) \
                .order_by(SubmissionBatch.submission_date.asc(), Profile.id.asc()) \
                .all()
        
        # --- Prepare data for "Profiles Submitted Per Day" Bar Chart ---
        num_days_in_month = calendar.monthrange(year, month)[1]
        bar_chart_labels = [str(day) for day in range(1, num_days_in_month + 1)]
        bar_chart_values = [0] * num_days_in_month 
        
        if db.engine.name == 'sqlite':
            daily_sums_query = db.session.query(
                    func.strftime('%d', SubmissionBatch.submission_date).cast(db.Integer), 
                    func.sum(SubmissionBatch.number_of_profiles)
                ).filter(
                    func.strftime('%Y-%m', SubmissionBatch.submission_date) == query_filter_year_month
                ).group_by(
                    func.strftime('%d', SubmissionBatch.submission_date) 
                ).all()
        else: 
            daily_sums_query = db.session.query(
                    db.extract('day', SubmissionBatch.submission_date).cast(db.Integer),
                    func.sum(SubmissionBatch.number_of_profiles)
                ).filter(
                    db.extract('year', SubmissionBatch.submission_date) == year,
                    db.extract('month', SubmissionBatch.submission_date) == month
                ).group_by(
                    db.extract('day', SubmissionBatch.submission_date)
                ).all()

        for day_num, total_profiles_for_day in daily_sums_query:
            if day_num and 1 <= day_num <= num_days_in_month: 
                bar_chart_values[day_num - 1] = total_profiles_for_day if total_profiles_for_day is not None else 0
        
        daily_trend_chart_data = {
            "labels": bar_chart_labels,
            "data": bar_chart_values,
            "month_name": month_name, 
            "year": year
        }

        # --- Prepare data for "Profile Distribution by Client" Pie Chart ---
        client_distribution = {}
        for profile_item in profiles_list_for_period: # Use the already fetched list of profiles
            client_name = profile_item.client if profile_item.client and profile_item.client.strip() else "Unspecified Client"
            client_distribution[client_name] = client_distribution.get(client_name, 0) + 1
        
        pie_chart_labels = list(client_distribution.keys())
        pie_chart_data_values = list(client_distribution.values())
        pie_chart_colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FFCD56', '#C9CBCF'] 
        # Ensure enough colors or a generator if many clients

        client_pie_chart_data = {
            "labels": pie_chart_labels,
            "data": pie_chart_data_values,
            "backgroundColors": pie_chart_colors[:len(pie_chart_labels)] 
        }
        
        report_data = {
            "period_display_name": period_display_name,
            "total_profiles_count": total_profiles_count,
            "profile_details_list": profiles_list_for_period,
            "daily_trend_chart_data": daily_trend_chart_data,
            "client_pie_chart_data": client_pie_chart_data
        }

    # Diagnostic prints (can be removed or commented out in production)
    if report_data:
        if 'daily_trend_chart_data' in report_data and report_data['daily_trend_chart_data']:
            print("---- SERVER-SIDE DAILY TREND CHART DATA ----")
            print(report_data['daily_trend_chart_data'])
        if 'client_pie_chart_data' in report_data and report_data['client_pie_chart_data']:
            print("---- SERVER-SIDE CLIENT PIE CHART DATA ----")
            print(report_data['client_pie_chart_data'])
    elif form.is_submitted() and not form.errors : # Form submitted but no report data (e.g. no submissions in period)
        print("---- SERVER-SIDE: Form submitted for monthly report, but no data found for the period. ----")
    
    return render_template('monthly_report.html', 
                           title='Monthly Report', 
                           form=form, 
                           report_data=report_data)


@main_bp.route('/profile/history', methods=['GET']) 
@login_required
def profile_history(): 
    page = request.args.get('page', 1, type=int)
    
    query_base = Profile.query \
        .join(SubmissionBatch, Profile.submission_batch_id == SubmissionBatch.id) \
        .join(User, SubmissionBatch.user_id == User.id)

    page_title = "Profile Submission History" 

    if current_user.role == 'manager':
        pagination = query_base \
            .order_by(SubmissionBatch.submission_date.desc(), SubmissionBatch.id.desc(), Profile.id.asc()) \
            .paginate(page=page, per_page=PROFILES_PER_PAGE, error_out=False)
        page_title = "All Profile Submissions (Chronological)"
    else: 
        pagination = query_base \
            .filter(SubmissionBatch.user_id == current_user.id) \
            .order_by(SubmissionBatch.submission_date.desc(), SubmissionBatch.id.desc(), Profile.id.asc()) \
            .paginate(page=page, per_page=PROFILES_PER_PAGE, error_out=False)
        page_title = "My Profile Submission History"
    
    profiles_on_page = pagination.items 

    return render_template('all_profiles_chronological.html', 
                           title=page_title, 
                           profiles=profiles_on_page,
                           pagination=pagination)

@main_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'manager':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('main.dashboard'))
    form = UserCreationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data 
        role = form.role.data
        new_user = User(username=username, role=role)
        new_user.set_password(password) 
        db.session.add(new_user)
        try:
            db.session.commit()
            flash(f'User "{username}" created successfully with role "{role}".', 'success')
            return redirect(url_for('main.create_user')) 
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user "{username}": {e}', 'danger')
            current_app.logger.error(f"Error creating user {username}: {e}")
    return render_template('create_user.html', title='Create New User', form=form)


@main_bp.route('/profile/<int:profile_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_profile(profile_id):
    profile_to_edit = Profile.query.get_or_404(profile_id)
    batch = profile_to_edit.batch 
    if not batch: 
        flash("Error: Profile is not associated with a batch.", "danger")
        return redirect(url_for('main.dashboard'))

    batch_owner_id = batch.user_id

    if current_user.id != batch_owner_id and current_user.role != 'manager':
        flash("You don't have permission to edit this profile.", "danger")
        return redirect(url_for('main.manage_batch_profiles', batch_id=batch.id))

    form = EditProfileForm(obj=profile_to_edit) 

    if form.validate_on_submit():
        profile_to_edit.profile_activity_date = form.profile_activity_date.data
        profile_to_edit.position = form.position.data
        profile_to_edit.client = form.client.data
        profile_to_edit.candidate_name = form.candidate_name.data
        profile_to_edit.contact_number = form.contact_number.data
        profile_to_edit.email_id = form.email_id.data
        profile_to_edit.total_experience = form.total_experience.data
        profile_to_edit.current_ctc = form.current_ctc.data
        profile_to_edit.expected_ctc = form.expected_ctc.data
        profile_to_edit.notice_period = form.notice_period.data
        profile_to_edit.feedback = form.feedback.data
        
        try:
            db.session.commit()
            flash(f'Profile "{profile_to_edit.candidate_name}" updated successfully!', 'success')
            return redirect(url_for('main.manage_batch_profiles', batch_id=batch.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {e}', 'danger')
            current_app.logger.error(f"Error updating profile {profile_to_edit.id}: {e}")
    
    return render_template('edit_profile.html', 
                           title=f"Edit Profile - {profile_to_edit.candidate_name}", 
                           form=form, 
                           profile=profile_to_edit)

@main_bp.route('/profile/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_profile(profile_id):
    profile_to_delete = Profile.query.get_or_404(profile_id)
    batch = profile_to_delete.batch 
    if not batch: 
        flash("Error: Profile is not associated with a batch, cannot update batch count.", "danger")
        return redirect(url_for('main.profile_history')) 

    batch_id_for_redirect = batch.id 

    if current_user.id != batch.user_id and current_user.role != 'manager':
        flash("You don't have permission to delete this profile.", "danger")
        return redirect(url_for('main.manage_batch_profiles', batch_id=batch_id_for_redirect))

    try:
        profile_name = profile_to_delete.candidate_name or f"Profile ID {profile_id}"
        
        if batch.number_of_profiles > 0: 
            batch.number_of_profiles -= 1
        
        db.session.delete(profile_to_delete)
        db.session.commit()
        flash(f'"{profile_name}" (ID: {profile_id}) has been deleted successfully. Batch profile count updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting profile: {e}', 'danger')
        current_app.logger.error(f"Error deleting profile {profile_id}: {e}")

    return redirect(url_for('main.manage_batch_profiles', batch_id=batch_id_for_redirect))

@main_bp.route('/batch/<int:batch_id>/profiles', methods=['GET'])
@login_required
def manage_batch_profiles(batch_id):
    batch = SubmissionBatch.query.get_or_404(batch_id)

    if batch.user_id != current_user.id and current_user.role != 'manager':
        flash("You don't have permission to view these profiles.", "danger")
        return redirect(url_for('main.dashboard'))
    
    profiles_in_batch = batch.profiles
    
    return render_template('manage_batch_profiles.html', 
                           title=f"Profiles in Batch ({batch.uploaded_filename} - {batch.submission_date.strftime('%Y-%m-%d')})", 
                           batch=batch, 
                           profiles=profiles_in_batch)

@main_bp.route('/batch/<int:batch_id>/delete', methods=['POST'])
@login_required
def delete_submission_batch(batch_id):
    batch_to_delete = SubmissionBatch.query.get_or_404(batch_id)

    if batch_to_delete.user_id != current_user.id and current_user.role != 'manager':
        # Allowing managers to delete any batch, or stick to owner only.
        # For now, let's stick to owner only to match the "by user" request for this function.
        # If managers need to delete any batch, this condition would be:
        # if batch_to_delete.user_id != current_user.id and current_user.role != 'manager':
        flash("You don't have permission to delete this submission batch.", "danger")
        return redirect(url_for('main.dashboard'))

    try:
        batch_filename = batch_to_delete.uploaded_filename or f"Batch ID {batch_to_delete.id}"
        
        db.session.delete(batch_to_delete) 
        db.session.commit()
        flash(f'Submission batch "{batch_filename}" and all its associated profiles have been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting submission batch: {e}', 'danger')
        current_app.logger.error(f"Error deleting submission batch {batch_id} by user {current_user.id}: {e}")

    return redirect(url_for('main.dashboard'))